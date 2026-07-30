import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import * as THREE from "three";
import type { Charger } from "../../api/types";
import { useCanvasResizeKick } from "../../hooks/useCanvasResizeKick";

const STATUS_COLOR: Record<string, string> = {
  available: "#10b981",
  occupied: "#22d3ee",
  offline: "#ef4444",
};

function Transformer({ loadFraction }: { loadFraction: number }) {
  const coilRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (coilRef.current) {
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 3) * 0.04 * loadFraction;
      coilRef.current.scale.setScalar(pulse);
    }
  });

  const heat = new THREE.Color().lerpColors(new THREE.Color("#10b981"), new THREE.Color("#ef4444"), Math.min(1, loadFraction));

  return (
    <group position={[0, 0, 0]}>
      <mesh position={[0, 0.5, 0]}>
        <cylinderGeometry args={[0.9, 1.1, 1, 24]} />
        <meshStandardMaterial color="#1e293b" metalness={0.6} roughness={0.35} />
      </mesh>
      <mesh ref={coilRef} position={[0, 1.15, 0]}>
        <torusGeometry args={[0.55, 0.12, 12, 32]} />
        <meshStandardMaterial color={heat} emissive={heat} emissiveIntensity={0.8} />
      </mesh>
      <mesh position={[0, 1.15, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.55, 0.12, 12, 32]} />
        <meshStandardMaterial color={heat} emissive={heat} emissiveIntensity={0.8} />
      </mesh>
    </group>
  );
}

function ChargerBay({ charger, position }: { charger: Charger; position: [number, number, number] }) {
  const color = STATUS_COLOR[charger.status] ?? "#64748b";
  const glowRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (glowRef.current && charger.status === "occupied") {
      const material = glowRef.current.material as THREE.MeshStandardMaterial;
      material.emissiveIntensity = 0.6 + Math.sin(state.clock.elapsedTime * 4) * 0.3;
    }
  });

  return (
    <group position={position}>
      <mesh position={[0, 0.6, 0]}>
        <boxGeometry args={[0.35, 1.2, 0.35]} />
        <meshStandardMaterial color="#0f172a" metalness={0.4} roughness={0.5} />
      </mesh>
      <mesh ref={glowRef} position={[0, 1.05, 0.19]}>
        <boxGeometry args={[0.22, 0.22, 0.02]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
      </mesh>
      {charger.status === "occupied" && (
        <EnergyBeam from={[0, 0.3, 0]} to={[-position[0] * 0.85, 1.15, -position[2] * 0.85]} color={color} />
      )}
    </group>
  );
}

function EnergyBeam({ from, to, color }: { from: [number, number, number]; to: [number, number, number]; color: string }) {
  const points = useMemo(() => [new THREE.Vector3(...from), new THREE.Vector3(...to)], [from, to]);
  return <Line points={points} color={color} lineWidth={1.5} transparent opacity={0.5} dashed dashScale={4} />;
}

export function StationScene({ chargers, loadFraction }: { chargers: Charger[]; loadFraction: number }) {
  useCanvasResizeKick();
  const positions = useMemo<[number, number, number][]>(() => {
    const radius = 2.6;
    return chargers.map((_, i) => {
      const angle = (i / Math.max(chargers.length, 1)) * Math.PI * 2;
      return [Math.cos(angle) * radius, 0, Math.sin(angle) * radius];
    });
  }, [chargers]);

  return (
    <Canvas camera={{ position: [4, 3.5, 5], fov: 45 }} dpr={[1, 1.5]}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 3]} intensity={1.1} />
      <pointLight position={[0, 3, 0]} intensity={0.4} color="#10b981" />
      <Transformer loadFraction={loadFraction} />
      {chargers.map((charger, i) => (
        <ChargerBay key={charger.id} charger={charger} position={positions[i]} />
      ))}
      <gridHelper args={[10, 20, "#1e293b", "#0f172a"]} position={[0, 0, 0]} />
      <OrbitControls enablePan={false} minDistance={3} maxDistance={12} maxPolarAngle={Math.PI / 2.1} />
    </Canvas>
  );
}
