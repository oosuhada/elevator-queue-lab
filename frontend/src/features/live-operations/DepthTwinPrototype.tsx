import { Canvas } from "@react-three/fiber";
import { useMemo } from "react";
import type { Snapshot } from "../../contracts/api";


const CAR_ORDER = ["L1", "L2", "L3", "H1", "H2", "H3"];

function floorY(floor: number): number {
  return -4.25 + ((floor - 1) / 17) * 8.5;
}

function SectionScene({ snapshot }: { snapshot: Snapshot }) {
  const queues = useMemo(() => Array.from({ length: 18 }, (_, index) => {
    const floor = index + 1;
    const queue = snapshot.queues[String(floor)] ?? { up: 0, down: 0 };
    return { floor, total: Number(queue.up) + Number(queue.down) };
  }), [snapshot.queues]);
  return (
    <>
      <ambientLight intensity={2.2} />
      <directionalLight position={[7, 8, 10]} intensity={1.5} />
      {Array.from({ length: 18 }, (_, index) => index + 1).map((floor) => (
        <mesh key={`floor-${floor}`} position={[0, floorY(floor), -0.42]}>
          <boxGeometry args={[8.8, floor === 1 ? 0.045 : 0.022, 0.5]} />
          <meshStandardMaterial color={floor === 1 ? "#6a979c" : "#8d8d87"} roughness={0.95} metalness={0.02} />
        </mesh>
      ))}
      {CAR_ORDER.map((carId, index) => (
        <mesh key={`shaft-${carId}`} position={[-2.5 + index * 1.02 + (index >= 3 ? 0.34 : 0), 0, 0]}>
          <boxGeometry args={[0.78, 8.7, 0.42]} />
          <meshStandardMaterial color={index < 3 ? "#d7e6e5" : "#d9dde0"} transparent opacity={0.17} roughness={1} />
        </mesh>
      ))}
      {snapshot.elevators.map((car, index) => (
        <mesh key={`car-${car.id}`} position={[-2.5 + index * 1.02 + (index >= 3 ? 0.34 : 0), floorY(car.floor), 0.24]}>
          <boxGeometry args={[0.62, 0.34, 0.58]} />
          <meshStandardMaterial color={car.load >= car.capacity ? "#d77642" : car.bank === "low" ? "#2e7e86" : "#3e5968"} roughness={0.55} metalness={0.12} />
        </mesh>
      ))}
      {queues.filter((queue) => queue.total > 0).map((queue) => (
        <mesh key={`queue-${queue.floor}`} position={[-4.65, floorY(queue.floor), 0.2]} scale={[1, Math.min(1.8, 0.45 + queue.total * 0.08), 1]}>
          <boxGeometry args={[0.16, 0.18, 0.22]} />
          <meshStandardMaterial color="#d77642" roughness={0.8} />
        </mesh>
      ))}
    </>
  );
}

export function DepthTwinPrototype({ snapshot }: { snapshot: Snapshot }) {
  return (
    <div className="depth-prototype" data-testid="depth-twin-prototype">
      <Canvas
        orthographic
        camera={{ position: [8.5, 5.8, 11], zoom: 54 }}
        dpr={[1, 1.35]}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      >
        <color attach="background" args={["#ecebe4"]} />
        <SectionScene snapshot={snapshot} />
      </Canvas>
      <div className="depth-prototype-caption">
        <strong>2.5D section study</strong>
        <span>Same simulator snapshot · no decorative state</span>
      </div>
    </div>
  );
}
