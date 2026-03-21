<?php

namespace App\Controller;

use App\DTO\Message;
use App\DTO\MessageMedia;
use App\Service\CouchDB;
use App\Service\MadelineTelegram;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Response;

use danog\MadelineProto\Exception;
use Symfony\Component\Serializer\SerializerInterface;

final class TelegramItemsController extends AbstractController
{
    public function __construct(
        private MadelineTelegram $madelineTelegram,
        private CouchDB $couchDB
    ){
    }

    #[Route('/telegram/download', name: 'app_telegram_items', methods: ["POST"])]
    public function index(Request $request, SerializerInterface $serializer ): StreamedResponse | JsonResponse
    {
        $downloadFolder = '/app/public/telegram_downloads';
        
        //Create download directory if it doesn't exist
        if (!file_exists($downloadFolder)) {
            mkdir($downloadFolder, 0777, true);
        }
        
        $madelineTelegram = $this->madelineTelegram;
        $couchDB = $this->couchDB;

        $response = new StreamedResponse(function () use ($request, $serializer, $madelineTelegram, $couchDB, $downloadFolder) {
            try {
                // Код, который может вызвать ошибку
            
                while (ob_get_level()) {
                    ob_end_clean();
                }

                $output = fopen('php://output', 'w');

                fwrite($output, 'Response started' . PHP_EOL); flush(); // 'w' - 'write

                $message = $serializer->deserialize($request->getContent(), Message::class, 'json', [
                    'groups' => ['Message.all']
                ]);
                $MadelineProto = $madelineTelegram->initMadelineProto();
                
                fwrite($output, "Logged in as: " . $MadelineProto->getSelf()['username'] . PHP_EOL); flush();
                
                // Resolve channel ID
                //$channel = $MadelineProto->getPwrChat('Warhammer40KSTLARG');
                //fwrite($output, "Accessing channel: {$channel['title']}" . PHP_EOL); flush();

                fwrite($output, "Message id: {$message->id}" . PHP_EOL); flush();
                
                $messages = $MadelineProto->messages->getHistory(
                    peer: \App\Const\Connection::GROUP_ID,
                    offset_id: $message->id,
                    add_offset: -1,
                    limit: 1
                );

                // For a single message:
                $messageFound = $messages['messages'][0];

                fwrite($output, "Count messages: " . count($messages['messages']) . PHP_EOL); flush();

                // $fileInfo = pathinfo($message['media']['document']['attributes'][0]['file_name'] ?? 'file');
                // $extension = $fileInfo['extension'] ?? 'unknown';
                // $fileName = "{$message['media']['document']['id']}_{$message['media']['_']}.{$extension}";
                
                // fwrite($output, "Downloading {$fileName}..." . PHP_EOL); flush();
                // $fileInfo = $MadelineProto->getInfo($messageFound['media']['document']['id']); // Получаем информацию о файле
                // $totalSize = $fileInfo['size']; // Общий размер файла

                // fwrite($output, print_r($messageFound['media'], true) . PHP_EOL); flush();

                // Download file
                $file = $MadelineProto->downloadToDir($messageFound['media'], $downloadFolder, function ($progress) use ($output) {
                    //$percent = $totalSize > 0 ? round(($downloadedBytes / $totalSize) * 100) : 0;
                    
                    // Обновляем прогресс только при изменении процентов
                    // if ($percent != $lastPercent) {
                    //     $lastPercent = $percent;
                        // fwrite($output, "\rПрогресс: {$percent}% ({$downloadedBytes}/{$totalSize} байт)";
                        // flush();
                    // };
                    fwrite($output, "Progress: {$progress}%" . PHP_EOL);
                    flush();
                });
                
                if ($file) {
                    fwrite($output, "Saved to: {$file}" . PHP_EOL); flush();
                } else {
                    fwrite($output, "Failed to download" . PHP_EOL); flush();
                }

                $couchdbConn = $couchDB->initCouchDB();
                $dbName = $couchDB->dbName;

                $response = $couchdbConn->get("{$dbName}/{$message->_id}");
                $existing = json_decode($response->getBody(), true);
                
                $existing['uploaded'] = true;
                // $doc = [];
                // Update with new revision
                // $doc['_rev'] = $existing['_rev'];
                $couchdbConn->put("{$dbName}/{$message->_id}", [
                    'json' => $existing
                ]);
            } catch (\Throwable $e) {
                fwrite($output, '[ERROR]' . $e->getMessage()) . PHP_EOL; flush();
            }
        });

        $response->headers->set('X-Accel-Buffering', 'no'); // Для Nginx
        $response->headers->set('Cache-Control', 'no-store');

        return $response;
    }

    #[Route('/telegram-downloads/download', name: 'app_telegram_download_file', methods: ["POST"])]
    public function downloadFile(Request $request): BinaryFileResponse|JsonResponse
    {
        $filePath = $request->request->get('filePath');
        if (!$filePath) {
            $data = json_decode($request->getContent(), true);
            $filePath = $data['filePath'] ?? null;
        }

        if (!$filePath) {
            return new JsonResponse(['error' => 'file_path is required'], Response::HTTP_BAD_REQUEST);
        }

        // Normalized path from frontend: /telegram_downloads/<file> or /stl_user_uploads/<file>
        $basename = basename($filePath);
        if ($basename === '' || str_contains($basename, '..')) {
            return new JsonResponse(['error' => 'Invalid file path'], Response::HTTP_BAD_REQUEST);
        }

        $projectDir = $this->getParameter('kernel.project_dir');
        if (str_starts_with((string) $filePath, '/stl_user_uploads/')) {
            $absolutePath = $projectDir . '/public/stl_user_uploads/' . $basename;
        } else {
            $absolutePath = $projectDir . '/public/telegram_downloads/' . $basename;
        }

        if (!file_exists($absolutePath) || !is_readable($absolutePath)) {
            return new JsonResponse(['error' => 'File not found'], Response::HTTP_NOT_FOUND);
        }

        return new BinaryFileResponse($absolutePath);
    }
}
