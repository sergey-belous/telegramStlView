import React, { Component } from "react";

import * as THREE from "three";
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from "three/examples/jsm/loaders/STLLoader";

import Messages from './Messages';
import { COUCHDB_AUTH, couchdbAllDocsUrl } from './couchdbConfig';

import "./App.css";

/**
 * В dev по умолчанию пустая строка → запросы на тот же origin (Vite), прокси в vite.config.ts → Symfony.
 * Задайте VITE_API_BASE, если фронт и API на разных доменах без прокси.
 */
const API_BASE =
  import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== ''
    ? import.meta.env.VITE_API_BASE
    : import.meta.env.DEV
      ? ''
      : 'http://localhost';

/** MIME, которые часто отдают браузеры для STL (расширение .stl обязательно дополнительно). */
const STL_MIME_TYPES = new Set([
  'model/stl',
  'application/sla',
  'application/vnd.ms-pki.stl',
  'application/octet-stream',
  'text/plain',
  '',
]);

function validateStlFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.stl')) {
    return `${file.name}: требуется расширение .stl`;
  }
  if (file.type && !STL_MIME_TYPES.has(file.type)) {
    return `${file.name}: недопустимый MIME «${file.type}»`;
  }
  return null;
}

function validateStlFileList(files: FileList | File[]): { valid: File[]; errors: string[] } {
  const list = Array.from(files as ArrayLike<File>);
  const errors: string[] = [];
  const valid: File[] = [];
  for (const f of list) {
    const err = validateStlFile(f);
    if (err) errors.push(err);
    else valid.push(f);
  }
  return { valid, errors };
}

const stlLoader = new STLLoader();

let mixer;

const clock = new THREE.Clock();
const container = document.getElementById( 'root' );

const renderer = new THREE.WebGLRenderer( { antialias: true } );
renderer.setPixelRatio( window.devicePixelRatio );
// renderer.setSize( window.innerWidth, window.innerHeight );
renderer.setSize( 1024, 800 );
container?.appendChild( renderer.domElement );

const scene = new THREE.Scene();
scene.background = new THREE.Color( 0xffffff );

// const camera = new THREE.PerspectiveCamera( 40, window.innerWidth / window.innerHeight, 1, 100 );
const camera = new THREE.PerspectiveCamera( 40, 1024 / 800, 1, 100 );
camera.position.set( 1, 1, 1 );
camera.lookAt(0, 0, 0);

const controls = new OrbitControls( camera, renderer.domElement );
controls.target.set( 0, 0, 0 );
controls.update();
controls.enablePan = false;
controls.enableDamping = true;

const groundGeometry = new THREE.PlaneGeometry(20, 20);
const groundMaterial = new THREE.MeshStandardMaterial({ 
    color: 0xffff00ff
});
const ground = new THREE.Mesh(groundGeometry, groundMaterial);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -1;
ground.receiveShadow = true; // поверхность принимает тени
scene.add(ground);

// // Scene setup
// const scene = new THREE.Scene();
// scene.background = new THREE.Color(0x111111);

// // Camera
// // const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
// // camera.position.z = 5;
// const camera = new THREE.PerspectiveCamera( 40, window.innerWidth / window.innerHeight, 1, 100 );
// // camera.position.set( 0.9728517749133652, 1.1044765132727201, 0.7316689528482836 );
// camera.position.set( 5, 2, 8 );
// // camera.lookAt( scene.position );


// // Renderer
// const renderer = new THREE.WebGLRenderer({ antialias: true });
// renderer.setSize(1024, 768);
// renderer.setPixelRatio(window.devicePixelRatio);
// // document.body.appendChild(renderer.domElement);

// // Controls
// const controls = new OrbitControls(camera, renderer.domElement);
// controls.target.set( 0, 0.5, 0 );
// controls.enableDamping = true;
// controls.dampingFactor = 0.05;

// // Lighting
// const ambientLight = new THREE.AmbientLight(0x404040);
// scene.add(ambientLight);

const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.5);
directionalLight1.position.set(1, 1, 1);
scene.add(directionalLight1);

const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.5);
directionalLight2.position.set(-1, -1, -1);
scene.add(directionalLight2);

const ambientLight = new THREE.AmbientLight(0x404040, 0.5); // color, intensity
scene.add(ambientLight);

// STL Loader
const loader = new STLLoader();

let currentModel: THREE.Mesh | null = null;

// Handle window resize
// window.addEventListener('resize', function() {
//     camera.aspect = window.innerWidth / window.innerHeight;
//     camera.updateProjectionMatrix();
//     renderer.setSize(window.innerWidth, window.innerHeight);
// });

type UserUploadDoc = {
  _id: string;
  fileName: string;
  savedUrl: string;
  createdAt?: string;
};

type CouchMessageDoc = {
  _id: string;
  savedUrl?: string;
  raw?: { media?: { document?: { attributes?: Array<{ file_name?: string }> } } };
};

type AppState = {
  scene: unknown;
  canvas?: unknown;
  messages?: CouchMessageDoc[];
  userUploads: UserUploadDoc[];
  userUploadsLoading: boolean;
  userUploadsLoadError: string | null;
  uploadClientErrors: string[];
  uploadServerErrors: Array<{ fileName?: string; error?: string; index?: number }>;
  png?: string;
  file?: Blob | File | null;
};

class App extends Component<Record<string, unknown>, AppState> {
  messagesComponentRef = React.createRef<InstanceType<typeof Messages>>();
  stlUploadInputRef = React.createRef<HTMLInputElement>();

  constructor(props: Record<string, unknown>) {
    super(props);

    this.state = {
      scene: null,
      userUploads: [],
      userUploadsLoading: true,
      userUploadsLoadError: null,
      uploadClientErrors: [],
      uploadServerErrors: [],
    };
  }

  componentDidMount() {
    this.sceneSetup();
    this.startAnimationLoop();
    void this.loadUserUploadsFromCouch();
  }

  /** Документы, созданные POST /api/stl/upload (CouchDB: type user_stl_upload / source user_upload). */
  loadUserUploadsFromCouch = async () => {
    this.setState({ userUploadsLoading: true, userUploadsLoadError: null });
    try {
      const basic = btoa(
        `${COUCHDB_AUTH.username}:${COUCHDB_AUTH.password}`,
      );
      const res = await fetch(couchdbAllDocsUrl(), {
        headers: {
          Accept: 'application/json',
          Authorization: `Basic ${basic}`,
        },
      });
      if (!res.ok) {
        throw new Error(`CouchDB ${res.status} ${res.statusText}`);
      }
      const data = (await res.json()) as {
        rows?: Array<{ doc?: Record<string, unknown> }>;
      };
      const rows = data.rows ?? [];
      const uploads: UserUploadDoc[] = [];

      for (const row of rows) {
        const doc = row.doc;
        if (!doc || String(doc._id ?? '').startsWith('_design')) {
          continue;
        }
        const isUserStl =
          doc.type === 'user_stl_upload' || doc.source === 'user_upload';
        if (
          !isUserStl ||
          typeof doc._id !== 'string' ||
          typeof doc.fileName !== 'string' ||
          typeof doc.savedUrl !== 'string'
        ) {
          continue;
        }
        uploads.push({
          _id: doc._id,
          fileName: doc.fileName,
          savedUrl: doc.savedUrl,
          createdAt:
            typeof doc.createdAt === 'string' ? doc.createdAt : undefined,
        });
      }

      uploads.sort((a, b) =>
        (b.createdAt ?? '').localeCompare(a.createdAt ?? ''),
      );

      this.setState({ userUploads: uploads, userUploadsLoading: false });
    } catch (e) {
      console.error('loadUserUploadsFromCouch', e);
      this.setState({
        userUploadsLoading: false,
        userUploadsLoadError:
          e instanceof Error ? e.message : 'Не удалось загрузить список из CouchDB',
      });
    }
  };

  sceneSetup = () => {
    document.querySelector('.rendered')?.appendChild(renderer.domElement);
    this.setState({ canvas: renderer });
  };

  addCustomSceneObjects = () => {
  };

  startAnimationLoop = () => {
    requestAnimationFrame(this.startAnimationLoop);

    controls.update();
    renderer.render(scene, camera);
  };

  /** Общая отрисовка STL из бинарного буфера (CouchDB / форма / Blob). */
  loadStlFromArrayBuffer = (arrayBuffer: ArrayBuffer) => {
    if (currentModel) {
      scene.remove(currentModel);
      currentModel = null;
    }

    // STLLoader иногда бросает RangeError на "битом" бинарном буфере
    // (например, если API вернул JSON/HTML ошибки вместо STL).
    let geometry: THREE.BufferGeometry;
    try {
      geometry = loader.parse(arrayBuffer);
    } catch (err) {
      const asText = new TextDecoder('utf-8').decode(arrayBuffer);
      geometry = loader.parse(asText);
      console.warn('STL parsed as text fallback:', err);
    }
    geometry.computeBoundingBox();
    const size = new THREE.Vector3();
    if (geometry.boundingBox) {
      geometry.boundingBox.getSize(size);
    }

    const material = new THREE.MeshPhongMaterial({
      color: 0xffffff,
      specular: 0x888888,
      shininess: 50,
      flatShading: true,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(0, 0, 0);
    mesh.scale.set(0.01, 0.01, 0.01);

    scene.add(mesh);
    currentModel = mesh;

    camera.updateProjectionMatrix();
    controls.update();

    const infoEl = document.getElementById('info');
    if (infoEl) {
      const vx = geometry.attributes.position.count;
      const dim =
        geometry.boundingBox
          ? `${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)}`
          : 'n/a';
      infoEl.innerHTML = `STL Model Loaded<br>Vertices: ${vx}<br>Dimensions: ${dim}`;
    }
  };

  handleFileRead = (e: Event | Blob) => {
    let file: Blob | undefined;
    if (e instanceof Event) {
      const t = e.target as HTMLInputElement;
      file = t.files?.[0] ?? undefined;
    } else if (e instanceof Blob) {
      file = e;
    }
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const result = event.target?.result;
      if (result instanceof ArrayBuffer) {
        this.loadStlFromArrayBuffer(result);
      }
    };
    reader.readAsArrayBuffer(file);
  };

  async urlToBlob(url: string) {
    try {
      // 1. Загружаем данные по URL
      
      const response = await fetch(`${API_BASE}/telegram-downloads/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json', // Указываем, что отправляем JSON
        },
        body: JSON.stringify({ filePath: url })
      });
      
      // 2. Проверяем статус ответа
      if (!response.ok) {
        throw new Error(`Ошибка HTTP: ${response.status}`);
      }

      const contentType = (response.headers.get('content-type') || '').toLowerCase();
      // Если прилетел JSON/HTML, почти наверняка это ошибка API, а не STL.
      if (contentType.includes('application/json') || contentType.includes('text/html')) {
        const body = await response.text();
        throw new Error(`Сервер вернул ${contentType || 'не STL'}: ${body.slice(0, 300)}`);
      }

      // 3. Преобразуем ответ в Blob
      const blob = await response.blob();
      if (blob.size < 6) {
        throw new Error(`Слишком маленький ответ (${blob.size} bytes), вероятно не STL`);
      }
      console.log('Blob создан:', blob);
      return blob;
      
    } catch (error) {
      console.error('Ошибка при загрузке файла:', error);
      throw error;
    }
  }

  loadFileTest(event:any, scene:any) {
    var fileObject = event.target.files[0];
    var reader = new FileReader();
    reader.onload = function () {
      var geometry = stlLoader.parse(this.result);
      console.warn(geometry);
      var material = new THREE.MeshPhongMaterial({
        emissive: 0x55ffff,
        color: 0xffffff,
        specular: null,
        shininess: 1,
        wireframe: true,
      });
      var mesh = new THREE.Mesh(geometry, material);
      mesh.rotation.set(-Math.PI / 2, 0, 0);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      scene.add(mesh);
    };
    reader.readAsArrayBuffer(fileObject);
  }

  fetchMessages = (_event: unknown) => {
    const child = this.messagesComponentRef.current as unknown as {
      state?: { data?: Array<CouchMessageDoc & { uploaded?: boolean }> };
    } | null;
    const rows = child?.state?.data;
    if (!rows) return;
    this.setState({
      messages: rows.filter((row) => row.uploaded === true),
    });
  };

  saveCanvasToState = (_event: unknown) => {
    const canvas = this.state.canvas as { domElement?: HTMLCanvasElement } | undefined;
    if (canvas?.domElement) {
      this.setState({ png: canvas.domElement.toDataURL() });
    }
  };

  logPng = (_event: unknown) => {
    console.log(this.state);
  };

  /**
   * Унифицированный рендер STL:
   * - `string` — _id документа из CouchDB (Telegram или user upload из списка)
   * - `File` — только что выбранный локальный файл
   * - `{ savedUrl }` — путь как в CouchDB (/telegram_downloads/... или /stl_user_uploads/...)
   * - `{ id }` — то же, что строка
   * - `{ file }` — явный File из формы
   */
  async renderStlModel(
    _e: unknown,
    source: string | File | { id?: string; savedUrl?: string; file?: File },
  ) {
    try {
      let buffer: ArrayBuffer | null = null;
      let blobForState: Blob | File | null = null;

      if (source instanceof File) {
        buffer = await source.arrayBuffer();
        blobForState = source;
      } else if (typeof source === 'string') {
        const doc =
          this.state.messages?.find((el) => el._id === source) ??
          this.state.userUploads.find((el) => el._id === source);
        const url = doc?.savedUrl;
        if (!url) {
          console.error('renderStlModel: нет savedUrl для id', source);
          return;
        }
        const blob = await this.urlToBlob(url);
        buffer = await blob.arrayBuffer();
        blobForState = blob;
      } else if (source.file) {
        buffer = await source.file.arrayBuffer();
        blobForState = source.file;
      } else if (source.savedUrl) {
        const blob = await this.urlToBlob(source.savedUrl);
        buffer = await blob.arrayBuffer();
        blobForState = blob;
      } else if (source.id) {
        const doc =
          this.state.messages?.find((el) => el._id === source.id) ??
          this.state.userUploads.find((el) => el._id === source.id);
        const url = doc?.savedUrl;
        if (!url) {
          console.error('renderStlModel: нет savedUrl для id', source.id);
          return;
        }
        const blob = await this.urlToBlob(url);
        buffer = await blob.arrayBuffer();
        blobForState = blob;
      }

      if (!buffer) return;

      this.loadStlFromArrayBuffer(buffer);
      this.setState({ file: blobForState });
    } catch (e) {
      console.error('renderStlModel failed:', e);
      const infoEl = document.getElementById('info');
      if (infoEl) {
        infoEl.innerHTML = `Ошибка рендера STL: ${e instanceof Error ? e.message : String(e)}`;
      }
    }
  }

  onStlFileInputChange = () => {
    const input = this.stlUploadInputRef.current;
    if (!input?.files?.length) {
      this.setState({ uploadClientErrors: [] });
      return;
    }
    const { errors } = validateStlFileList(input.files);
    this.setState({ uploadClientErrors: errors });
  };

  handleStlUploadSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const input = this.stlUploadInputRef.current;
    if (!input?.files?.length) return;

    const { valid, errors } = validateStlFileList(input.files);
    this.setState({ uploadClientErrors: errors, uploadServerErrors: [] });
    if (!valid.length) return;

    // Индексированные имена стабильно мапятся в $_FILES['stl_files'] в PHP; третий аргумент — имя файла в multipart.
    const formData = new FormData();
    valid.forEach((f, i) => formData.append(`stl_files[${i}]`, f, f.name));

    try {
      const res = await fetch(`${API_BASE}/api/stl/upload`, {
        method: 'POST',
        body: formData,
        // не задавать Content-Type вручную — браузер добавит boundary для multipart
      });
      const data = await res.json();
      void this.loadUserUploadsFromCouch();
      if (data.documents?.length) {
        input.value = '';
      }
      this.setState({
        uploadServerErrors:
          data.errors?.length
            ? data.errors
            : !data.documents?.length
              ? [{ error: data.error || `HTTP ${res.status}` }]
              : [],
      });
    } catch (err) {
      console.error(err);
      const isNetwork =
        err instanceof TypeError &&
        (String(err.message).includes('fetch') || String(err.message).includes('Failed to fetch'));
      this.setState({
        uploadServerErrors: [
          {
            error: isNetwork
              ? 'Нет связи с API. В режиме разработки используйте относительные URL (VITE_API_BASE не задан) и прокси Vite; в Docker задайте VITE_DEV_PROXY_TARGET=http://symfony-php-apache для сервиса nodejs.'
              : err instanceof Error
                ? err.message
                : String(err),
          },
        ],
      });
    }
  };

  render() {
    const {
      messages,
      userUploads,
      userUploadsLoading,
      userUploadsLoadError,
      uploadClientErrors,
      uploadServerErrors,
    } = this.state;

    return (
      <div>
        <Messages ref={this.messagesComponentRef} />
        <div className="canvas-controls">
          <h3>STL Models Storage — загрузка файлов</h3>
          <form encType="multipart/form-data" onSubmit={(e) => this.handleStlUploadSubmit(e)}>
            <label>
              Выберите один или несколько .stl (проверка MIME + расширение):{' '}
              <input
                ref={this.stlUploadInputRef}
                type="file"
                name="stl_files"
                accept=".stl,model/stl,application/sla"
                multiple
                onChange={this.onStlFileInputChange}
              />
            </label>
            <button type="submit">Загрузить на сервер (CouchDB + диск)</button>
          </form>
          {uploadClientErrors?.length ? (
            <ul className="upload-errors">
              {uploadClientErrors.map((msg, i) => (
                <li key={i}>{msg}</li>
              ))}
            </ul>
          ) : null}
          {uploadServerErrors?.length ? (
            <ul className="upload-errors server">
              {uploadServerErrors.map((row, i) => (
                <li key={i}>
                  {row.fileName ? `${row.fileName}: ` : ''}
                  {row.error ?? JSON.stringify(row)}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="user-uploads-block">
            <h4>Загруженные на сервер модели (CouchDB)</h4>
            {userUploadsLoading ? (
              <p className="user-uploads-status">Загрузка списка…</p>
            ) : userUploadsLoadError ? (
              <p className="user-uploads-status error">
                {userUploadsLoadError}{' '}
                <button type="button" onClick={() => void this.loadUserUploadsFromCouch()}>
                  Повторить
                </button>
              </p>
            ) : userUploads.length === 0 ? (
              <p className="user-uploads-status">Пока нет файлов — загрузите .stl выше.</p>
            ) : (
              <ul className="user-uploads-list">
                {userUploads.map((doc) => (
                  <li key={doc._id}>
                    <span className="user-upload-name">{doc.fileName}</span>{' '}
                    <button type="button" onClick={(e) => this.renderStlModel(e, { id: doc._id })}>
                      Показать в viewer
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button onClick={(event) => this.fetchMessages(event)}>Fecth downloadedModels from telegram database component</button>
          <ul>
          {messages ? messages.map((doc) => (
              <li key={doc._id} className="uploaded">
                <pre>{doc.raw?.media?.document?.attributes?.[0]?.file_name}</pre>
                <button onClick={(e) => this.renderStlModel(e, doc._id)}>Render Model</button>
              </li>
            )) : 'No messages fetched from Messages.Component' }
          </ul>
          <div id="info"></div>
        </div>
        <div className="rendered"></div>
        <hr/>
        <button onClick={(e) => this.saveCanvasToState(e)}>saveCanvasToState</button><hr/>
        <button onClick={(e) => this.logPng(e)}>logPng</button>
      </div>
      
    );
  }
}

export default App;