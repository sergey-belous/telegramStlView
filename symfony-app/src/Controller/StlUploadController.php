<?php

declare(strict_types=1);

namespace App\Controller;

use App\Service\CouchDB;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\File\UploadedFile;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

/**
 * User STL uploads: files on disk + metadata in CouchDB (stl models storage).
 */
final class StlUploadController extends AbstractController
{
    /** @var list<string> */
    private const ALLOWED_MIME_TYPES = [
        'model/stl',
        'application/sla',
        'application/vnd.ms-pki.stl',
        'application/octet-stream',
        'text/plain',
    ];

    public function __construct(
        private readonly CouchDB $couchDB,
    ) {
    }

    #[Route('/api/stl/upload', name: 'api_stl_upload', methods: ['POST'])]
    public function upload(Request $request): JsonResponse
    {
        $projectDir = $this->getParameter('kernel.project_dir');
        $uploadDir = $projectDir . '/public/stl_user_uploads';
        if (!is_dir($uploadDir) && !mkdir($uploadDir, 0775, true) && !is_dir($uploadDir)) {
            return new JsonResponse(['ok' => false, 'error' => 'Cannot create upload directory'], Response::HTTP_INTERNAL_SERVER_ERROR);
        }

        $files = self::resolveUploadedStlFiles($request);

        if ($files === []) {
            $contentType = strtolower((string) $request->headers->get('Content-Type', ''));
            $isMultipart = str_starts_with($contentType, 'multipart/form-data');
            $payload = [
                'ok' => false,
                'error' => $isMultipart
                    ? 'Файлы не попали в PHP ($_FILES пуст). Частая причина: превышен post_max_size — увеличьте upload_max_filesize/post_max_size для Apache PHP (в образе добавлен 99-uploads.ini; пересоберите контейнер).'
                    : 'No files (ожидается multipart/form-data, поля stl_files / stl_files[] / stl_files[0]…)',
            ];
            if ($this->getParameter('kernel.debug')) {
                $payload['debug'] = [
                    'contentType' => $request->headers->get('Content-Type'),
                    'contentLength' => $request->headers->get('Content-Length'),
                    'fileBagKeys' => array_keys($request->files->all()),
                ];
            }

            return new JsonResponse($payload, Response::HTTP_BAD_REQUEST);
        }

        $couch = $this->couchDB->initCouchDB();
        $dbName = $this->couchDB->dbName;

        $documents = [];
        $errors = [];
        /** @var array<string, true> Хеши sha256 (hex), уже сохранённые в рамках этого запроса */
        $hashesCommittedInBatch = [];

        foreach ($files as $index => $file) {
            if (!$file->isValid()) {
                $errors[] = ['index' => $index, 'error' => 'Invalid upload: ' . $file->getErrorMessage()];
                continue;
            }

            $originalName = $file->getClientOriginalName();
            if (!str_ends_with(strtolower($originalName), '.stl')) {
                $errors[] = ['fileName' => $originalName, 'error' => 'Only .stl files are allowed'];
                continue;
            }

            $mime = $file->getMimeType() ?? '';
            if ($mime !== '' && !in_array($mime, self::ALLOWED_MIME_TYPES, true)) {
                $errors[] = ['fileName' => $originalName, 'error' => 'Unsupported MIME type: ' . $mime];
                continue;
            }

            $pathForHash = $file->getRealPath();
            if ($pathForHash === false || !is_readable($pathForHash)) {
                $errors[] = ['fileName' => $originalName, 'error' => 'Cannot read uploaded file for hashing'];
                continue;
            }

            $contentHash = hash_file('sha256', $pathForHash);
            if ($contentHash === false) {
                $errors[] = ['fileName' => $originalName, 'error' => 'Failed to compute file hash'];
                continue;
            }

            if (isset($hashesCommittedInBatch[$contentHash])) {
                $errors[] = [
                    'fileName' => $originalName,
                    'error' => 'Дубликат в этом же запросе: файл с таким содержимым уже добавлен.',
                    'code' => 'duplicate_hash_batch',
                ];
                continue;
            }

            $existing = $this->findUserStlByContentHash($couch, $dbName, $contentHash);
            if ($existing !== null) {
                $errors[] = [
                    'fileName' => $originalName,
                    'error' => sprintf(
                        'Файл с таким содержимым уже загружен как «%s».',
                        $existing['fileName'] ?? $existing['_id'] ?? 'unknown'
                    ),
                    'code' => 'duplicate_hash',
                    'existingId' => $existing['_id'] ?? null,
                ];
                continue;
            }

            $safeBase = bin2hex(random_bytes(16)) . '.stl';
            try {
                $file->move($uploadDir, $safeBase);
            } catch (\Throwable $e) {
                $errors[] = ['fileName' => $originalName, 'error' => 'Failed to store file'];
                continue;
            }

            $savedUrl = '/stl_user_uploads/' . $safeBase;
            $docId = 'user_stl_' . bin2hex(random_bytes(8));

            $doc = [
                '_id' => $docId,
                'type' => 'user_stl_upload',
                'source' => 'user_upload',
                'fileName' => $originalName,
                'savedUrl' => $savedUrl,
                'mimeType' => $mime,
                'contentHash' => $contentHash,
                'uploaded' => true,
                'createdAt' => (new \DateTimeImmutable('now'))->format(DATE_ATOM),
            ];

            try {
                $couch->put($dbName . '/' . $docId, ['json' => $doc]);
            } catch (\Throwable $e) {
                @unlink($uploadDir . '/' . $safeBase);
                $errors[] = ['fileName' => $originalName, 'error' => 'CouchDB error: ' . $e->getMessage()];
                continue;
            }

            $hashesCommittedInBatch[$contentHash] = true;

            $documents[] = [
                '_id' => $docId,
                'fileName' => $originalName,
                'savedUrl' => $savedUrl,
            ];
        }

        return new JsonResponse([
            'ok' => $documents !== [],
            'documents' => $documents,
            'errors' => $errors,
        ], $documents !== [] ? Response::HTTP_CREATED : Response::HTTP_BAD_REQUEST);
    }

    /**
     * @return array<string, mixed>|null документ с полями _id, fileName, savedUrl при наличии
     */
    private function findUserStlByContentHash(\GuzzleHttp\Client $couch, string $dbName, string $sha256Hex): ?array
    {
        try {
            $response = $couch->post($dbName . '/_find', [
                'json' => [
                    'selector' => [
                        'type' => 'user_stl_upload',
                        'contentHash' => $sha256Hex,
                    ],
                    'limit' => 1,
                    'fields' => ['_id', 'fileName', 'savedUrl', 'contentHash'],
                ],
            ]);
            $data = json_decode($response->getBody()->getContents(), true);
            if (!\is_array($data)) {
                return null;
            }
            $docs = $data['docs'] ?? [];

            return \is_array($docs) && isset($docs[0]) && \is_array($docs[0]) ? $docs[0] : null;
        } catch (\Throwable) {
            return null;
        }
    }

    /**
     * Собирает все UploadedFile из запроса: stl_files, stl_files[], вложенные массивы, любые ключи FileBag.
     */
    private static function resolveUploadedStlFiles(Request $request): array
    {
        $fromNamed = self::normalizeUploadedFileList($request->files->get('stl_files'));
        if ($fromNamed !== []) {
            return $fromNamed;
        }
        $fromBracketName = self::normalizeUploadedFileList($request->files->get('stl_files[]'));
        if ($fromBracketName !== []) {
            return $fromBracketName;
        }

        $merged = [];
        foreach ($request->files->all() as $value) {
            foreach (self::normalizeUploadedFileList($value) as $uf) {
                $merged[] = $uf;
            }
        }

        return $merged;
    }

    /**
     * @return list<UploadedFile>
     */
    private static function normalizeUploadedFileList(mixed $raw): array
    {
        if ($raw instanceof UploadedFile) {
            return [$raw];
        }
        if (!is_array($raw)) {
            return [];
        }

        $out = [];
        foreach ($raw as $item) {
            if ($item instanceof UploadedFile) {
                $out[] = $item;
                continue;
            }
            if (is_array($item)) {
                foreach (self::normalizeUploadedFileList($item) as $nested) {
                    $out[] = $nested;
                }
            }
        }

        return $out;
    }
}
