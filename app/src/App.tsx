import React, { Component } from "react";
import ReactDOM from "react-dom";

import * as THREE from "three";
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { STLLoader } from "three/examples/jsm/loaders/STLLoader";

import Messages from './Messages';

import "./App.css";

const rootElement = document.getElementById("root");

const stlLoader = new STLLoader();

let mixer;

const clock = new THREE.Clock();
const container = document.getElementById( 'root' );

const renderer = new THREE.WebGLRenderer( { antialias: true } );
renderer.setPixelRatio( window.devicePixelRatio );
renderer.setSize( window.innerWidth, window.innerHeight );
container.appendChild( renderer.domElement );

const pmremGenerator = new THREE.PMREMGenerator( renderer );

const scene = new THREE.Scene();
scene.background = new THREE.Color( 0xffffff );
// scene.environment = pmremGenerator.fromScene( new RoomEnvironment(), 0.04 ).texture;

const camera = new THREE.PerspectiveCamera( 40, window.innerWidth / window.innerHeight, 1, 100 );
camera.position.set( 1, 1, 1 );
camera.lookAt(0, 0, 0);

const controls = new OrbitControls( camera, renderer.domElement );
controls.target.set( 0, 0, 0 );
controls.update();
controls.enablePan = false;
controls.enableDamping = true;

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

let currentModel = null;

// Handle window resize
// window.addEventListener('resize', function() {
//     camera.aspect = window.innerWidth / window.innerHeight;
//     camera.updateProjectionMatrix();
//     renderer.setSize(window.innerWidth, window.innerHeight);
// });

class App extends Component {
  constructor(props:any) {
    super(props);

    this.state = {
      scene: null,
    };

    this.messagesComponentRef = React.createRef<HTMLDivElement>();
  }

  componentDidMount() {
    this.sceneSetup();
    this.startAnimationLoop();
  }

  sceneSetup = () => {
    document.querySelector('.rendered')?.appendChild(renderer.domElement);
  };

  addCustomSceneObjects = () => {
  };

  startAnimationLoop = () => {
    requestAnimationFrame(this.startAnimationLoop);

    controls.update();
    renderer.render(scene, camera);
  };

  handleFileRead = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(event) {
        // Remove previous model if exists
        if (currentModel) {
            scene.remove(currentModel);
        }
        
        // Load new model
        const geometry = loader.parse(event.target.result);
        
        // Compute center for positioning
        // geometry.computeBoundingBox();
        // const center = new THREE.Vector3();
        // geometry.boundingBox.getCenter(center);
        
        // Create material
        const material = new THREE.MeshPhongMaterial({
            color: 0xFFFFFF,
            specular: 0x888888,
            shininess: 50,
            flatShading: true
        });
        
        // Create mesh
        const mesh = new THREE.Mesh(geometry, material);
        
        // Center the model
        // mesh.position.x = center.x;
        // mesh.position.y = center.y;
        // mesh.position.z = center.z;
        // mesh.position.set( 1, 1, 0 );

				mesh.position.set( 0, 0, 0 );

        const matrix = new THREE.Matrix4();
        matrix.makeRotationX(-Math.PI / 2);
        mesh.applyMatrix4(matrix);
        
        console.log(
          mesh.rotation.x,
          mesh.rotation.y,
          mesh.rotation.z,
        );
        // mesh.quaternion.setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2);

        mesh.scale.set( 0.01, 0.01, 0.01 );

        mesh.traverse((node) => {
          if (node.isMesh) {
            // Enable AO if the model has AO textures
            node.material.aoMapIntensity = 1.0; // Adjust intensity (0-1)
            node.material.needsUpdate = true;
          }
        });

        // Add to scene
        scene.add(mesh);
        currentModel = mesh;
      
        camera.updateProjectionMatrix();

        // Adjust camera to fit model
        // const size = geometry.boundingBox.getSize(new THREE.Vector3());
        // const maxDim = Math.max(size.x, size.y, size.z);
        // const fov = camera.fov * (Math.PI / 180);
        // let cameraZ = Math.abs(maxDim / 2 * Math.tan(fov * 2));
        
        // // Add some padding
        // cameraZ *= 1.5;
        // camera.position.z = cameraZ;
        
        // Reset camera target
        //controls.target.copy(center);
        controls.update();
        
        // Update info
        document.getElementById('info').innerHTML = `
            STL Model Loaded<br>
            Vertices: ${geometry.attributes.position.count}<br>
            Dimensions: ${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)}
        `;
    };
    
    reader.readAsArrayBuffer(file);
  };

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

  fetchMessages(event) {
    this.setState({
      messages: this.messagesComponentRef.current.state.data.filter((row) => row.uploaded === true)
    })
    console.log(this.state.messages)
  }

  render() {
    const { messages } = this.state;

    console.log('___>>>>&&& ' , messages)

    return (
      <div>
        <Messages ref={this.messagesComponentRef} />
        <div className = "canvas-controls">
          <button onClick={(event) => this.fetchMessages(event)}>Fecth downloadedModels from child component</button>
          <ul>
          {messages ? messages.map((doc) => (
              <li key={doc._id} className="uploaded">
                <pre>{doc.raw.media?.document?.attributes[0]?.file_name}</pre>
              </li>
            )) : 'No messages fetched from Messages.Component' }
          </ul>
          <input
            type="file"
            id="file-input"
            onChange={(event) => this.handleFileRead(event)}
            accept=".stl"
          />
          <div id="info"></div>
        </div>
        <div className="rendered"></div>
      </div>
      
    );
  }
}

export default App;