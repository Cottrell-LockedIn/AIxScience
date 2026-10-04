import {
  Component,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ErrorInfo,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Group, PlaneGeometry, SRGBColorSpace, TextureLoader } from "three";
import "./MaterialScene.css";

export type MaterialLayer = {
  /** A versioned, spatially aligned mask image. Do not pass inferred layers here. */
  imageUrl: string;
  label: string;
  id: string;
  /** Must be asserted by the artifact manifest before this can be rendered. */
  verified: true;
};

export type MaterialSceneProps = {
  imageUrl: string;
  fieldId: string;
  /** Exact aligned masks from the completed engine run, when available. */
  layers?: MaterialLayer[];
};

type View = "front" | "left" | "right";

const VIEWS: Record<View, [number, number, number]> = {
  front: [0, 0, 0],
  left: [0.14, -0.38, 0.04],
  right: [0.14, 0.38, -0.04],
};
const EMPTY_LAYERS: MaterialLayer[] = [];

class SceneBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // The flat image is intentionally the useful fallback for unsupported WebGL.
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return reduced;
}

type SceneSource = { id: string; label: string; imageUrl: string; original?: boolean };

function TexturedPlates({
  imageUrl,
  rotation,
  reducedMotion,
  layers,
  separated,
}: {
  imageUrl: string;
  rotation: [number, number, number];
  reducedMotion: boolean;
  layers: MaterialLayer[];
  separated: boolean;
}) {
  const sources = useMemo<SceneSource[]>(
    () => [{ id: "original", label: "Original BSE image", imageUrl, original: true }, ...layers.slice(0, 3)],
    [imageUrl, layers],
  );
  const textures = useLoader(TextureLoader, sources.map((source) => source.imageUrl));
  const plate = useRef<Group>(null);
  const layersRef = useRef<Array<Group | null>>([]);
  const target = useRef(rotation);
  const transitionStarted = useRef(0);
  const { invalidate } = useThree();
  const originalImage = textures[0]?.image as { width?: number; height?: number } | undefined;
  const aspect = originalImage?.width && originalImage?.height ? originalImage.width / originalImage.height : 5.9 / 3.8;
  const planeWidth = 5.9;
  const planeHeight = planeWidth / aspect;

  useEffect(() => {
    target.current = rotation;
    transitionStarted.current = performance.now();
    invalidate();
  }, [rotation, invalidate]);

  useEffect(() => {
    transitionStarted.current = performance.now();
    invalidate();
  }, [separated, invalidate]);

  useEffect(() => {
    textures.forEach((texture) => {
      texture.colorSpace = SRGBColorSpace;
      texture.needsUpdate = true;
    });
  }, [textures]);

  useFrame((_state, delta) => {
    if (!plate.current) return;
    const object = plate.current.rotation;
    const next = target.current;
    const snap = reducedMotion || performance.now() - transitionStarted.current >= 220;
    const rate = snap ? 1 : 1 - Math.exp(-delta * 30);
    object.x += (next[0] - object.x) * rate;
    object.y += (next[1] - object.y) * rate;
    object.z += (next[2] - object.z) * rate;

    let resting =
      Math.abs(next[0] - object.x) < 0.002 &&
      Math.abs(next[1] - object.y) < 0.002 &&
      Math.abs(next[2] - object.z) < 0.002;
    layersRef.current.forEach((layer, index) => {
      if (!layer) return;
      const targetZ = separated ? (index - (sources.length - 1) / 2) * 0.6 : index * 0.012;
      const layerRate = snap ? 1 : 1 - Math.exp(-delta * 30);
      layer.position.z += (targetZ - layer.position.z) * layerRate;
      if (Math.abs(targetZ - layer.position.z) >= 0.002) resting = false;
    });
    if (!resting) invalidate();
  });

  return (
    <group ref={plate} rotation={VIEWS.front}>
      {sources.map((source, index) => (
        <group
          key={source.id}
          ref={(node) => { layersRef.current[index] = node; }}
          position={[0, 0, index * 0.012]}
        >
          <mesh>
            <planeGeometry args={[planeWidth, planeHeight]} />
            <meshBasicMaterial
              map={textures[index]}
              toneMapped={false}
              transparent={!source.original}
              opacity={source.original ? 1 : 0.9}
            />
          </mesh>
          <lineSegments position={[0, 0, -0.006]}>
            <edgesGeometry args={[new PlaneGeometry(planeWidth, planeHeight)]} />
            <lineBasicMaterial color={source.original ? "#7040dc" : "#8d72c5"} transparent opacity={0.66} />
          </lineSegments>
        </group>
      ))}
    </group>
  );
}

function Scene({
  imageUrl,
  rotation,
  reducedMotion,
  layers,
  separated,
}: {
  imageUrl: string;
  rotation: [number, number, number];
  reducedMotion: boolean;
  layers: MaterialLayer[];
  separated: boolean;
}) {
  return (
    <Canvas
      className="material-scene__canvas"
      dpr={[1, 1.5]}
      frameloop="demand"
      camera={{ position: [0, 0, 6.9], fov: 32 }}
      gl={{ antialias: true, alpha: false, powerPreference: "low-power" }}
      onCreated={({ gl, invalidate }) => {
        gl.setClearColor("#f7f7f4", 1);
        invalidate();
      }}
    >
      <color attach="background" args={["#f7f7f4"]} />
      <ambientLight intensity={0.85} />
      <Suspense fallback={null}>
        <TexturedPlates
          imageUrl={imageUrl}
          rotation={rotation}
          reducedMotion={reducedMotion}
          layers={layers}
          separated={separated}
        />
      </Suspense>
    </Canvas>
  );
}

function FlatFallback({ imageUrl, fieldId }: Pick<MaterialSceneProps, "imageUrl" | "fieldId">) {
  return (
    <div className="material-scene__fallback">
      <img src={imageUrl} alt={`Original micrograph for ${fieldId}`} />
      <span>3D view unavailable — showing the original image.</span>
    </div>
  );
}

/**
 * A presentation-only perspective of one original micrograph.
 * It never invents material layers or physical depth from a 2D field.
 */
export default function MaterialScene({ imageUrl, fieldId, layers = EMPTY_LAYERS }: MaterialSceneProps) {
  const [view, setView] = useState<View>("front");
  const [rotation, setRotation] = useState<[number, number, number]>(VIEWS.front);
  const [separated, setSeparated] = useState(false);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ pointerId: number; x: number; y: number; rotation: [number, number, number] } | null>(null);
  const reducedMotion = useReducedMotion();
  const exactLayers = useMemo(
    () => layers.filter((layer) => layer.verified === true && layer.imageUrl.trim().length > 0).slice(0, 3),
    [layers],
  );

  const setPresetView = (next: View) => {
    setView(next);
    setRotation(VIEWS[next]);
  };

  const beginDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    drag.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, rotation };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };

  const moveDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (!start || start.pointerId !== event.pointerId) return;
    const next: [number, number, number] = [
      Math.max(-0.52, Math.min(0.52, start.rotation[0] - (event.clientY - start.y) * 0.003)),
      Math.max(-0.68, Math.min(0.68, start.rotation[1] + (event.clientX - start.x) * 0.003)),
      0,
    ];
    setView("front");
    setRotation(next);
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId === event.pointerId) drag.current = null;
    setDragging(false);
  };

  return (
    <section className="material-scene" aria-label={`Material perspective for ${fieldId}`}>
      <div className="material-scene__topline">
        <div>
          <p className="material-scene__label">Material perspective</p>
          <h3>{fieldId}</h3>
        </div>
        <span className="material-scene__status">{separated ? "Original + phase layers" : "Aligned image layers"}</span>
      </div>

      <div
        className={`material-scene__viewport ${dragging ? "is-dragging" : ""}`}
        onPointerDown={beginDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        aria-label="Drag the image to change its perspective"
      >
        <SceneBoundary fallback={<FlatFallback imageUrl={imageUrl} fieldId={fieldId} />}>
          <Scene
            imageUrl={imageUrl}
            rotation={rotation}
            reducedMotion={reducedMotion}
            layers={exactLayers}
            separated={separated}
          />
        </SceneBoundary>
      </div>

      <div className="material-scene__controls" aria-label="Perspective controls">
        <button type="button" className={view === "left" ? "is-active" : ""} onClick={() => setPresetView("left")}>
          Tilt left
        </button>
        <button type="button" className={view === "front" ? "is-active" : ""} onClick={() => setPresetView("front")}>
          Front
        </button>
        <button type="button" className={view === "right" ? "is-active" : ""} onClick={() => setPresetView("right")}>
          Tilt right
        </button>
        {exactLayers.length > 0 && (
          <button type="button" className={separated ? "is-active" : ""} onClick={() => { const next = !separated; setSeparated(next); setView(next ? "left" : "front"); setRotation(next ? [0.72, -0.4, -0.06] : VIEWS.front); }}>
            {separated ? "Stack layers" : "Separate layers"}
          </button>
        )}
      </div>

      <div className="material-scene__notes">
        <p>A 2D image shown in perspective. Depth is illustrative.</p>
        {exactLayers.length === 0 ? (
          <p className="material-scene__unavailable">Segmentation layers unavailable for this engine release.</p>
        ) : (
          <p className="material-scene__available">
            {exactLayers.length} exact, versioned segmentation {exactLayers.length === 1 ? "layer is" : "layers are"} from this run. Separate them to compare the measured regions.
          </p>
        )}
      </div>
    </section>
  );
}
