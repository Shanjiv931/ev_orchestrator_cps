import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { useCanvasResizeKick } from "../../hooks/useCanvasResizeKick";

interface CarSceneProps {
  colorHex: string;
  vehicleClass: "2W" | "3W" | "4W";
  batteryPct: number;
  isCharging: boolean;
}

function Wheel({ position }: { position: [number, number, number] }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.x += delta * 2; });
  return (
    <mesh ref={ref} position={position} rotation={[0, 0, Math.PI / 2]}>
      <cylinderGeometry args={[0.32, 0.32, 0.22, 20]} />
      <meshStandardMaterial color="#111827" roughness={0.8} />
    </mesh>
  );
}

function FourWheelCar({ colorHex }: { colorHex: string }) {
  return (
    <group>
      <mesh position={[0, 0.45, 0]}>
        <boxGeometry args={[2.2, 0.5, 1]} />
        <meshStandardMaterial color={colorHex} metalness={0.5} roughness={0.3} />
      </mesh>
      <mesh position={[-0.2, 0.85, 0]}>
        <boxGeometry args={[1.2, 0.4, 0.9]} />
        <meshStandardMaterial color={colorHex} metalness={0.5} roughness={0.3} />
      </mesh>
      <Wheel position={[0.75, 0.32, 0.55]} />
      <Wheel position={[0.75, 0.32, -0.55]} />
      <Wheel position={[-0.75, 0.32, 0.55]} />
      <Wheel position={[-0.75, 0.32, -0.55]} />
    </group>
  );
}

function TwoWheeler({ colorHex }: { colorHex: string }) {
  return (
    <group>
      <mesh position={[0, 0.55, 0]}>
        <boxGeometry args={[1.3, 0.28, 0.35]} />
        <meshStandardMaterial color={colorHex} metalness={0.5} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.9, -0.3]}>
        <boxGeometry args={[0.3, 0.5, 0.25]} />
        <meshStandardMaterial color={colorHex} metalness={0.5} roughness={0.3} />
      </mesh>
      <Wheel position={[0.6, 0.32, 0]} />
      <Wheel position={[-0.6, 0.32, 0]} />
    </group>
  );
}

function ThreeWheeler({ colorHex }: { colorHex: string }) {
  return (
    <group>
      <mesh position={[0, 0.5, 0]}>
        <boxGeometry args={[1.6, 0.5, 1.1]} />
        <meshStandardMaterial color={colorHex} metalness={0.5} roughness={0.3} />
      </mesh>
      <Wheel position={[0.5, 0.32, 0]} />
      <Wheel position={[-0.5, 0.32, 0.5]} />
      <Wheel position={[-0.5, 0.32, -0.5]} />
    </group>
  );
}

function ChargeAura({ batteryPct, isCharging }: { batteryPct: number; isCharging: boolean }) {
  const ref = useRef<THREE.Mesh>(null);
  const color = batteryPct > 50 ? "#10b981" : batteryPct > 20 ? "#f59e0b" : "#ef4444";
  useFrame((state) => {
    if (ref.current && isCharging) {
      const material = ref.current.material as THREE.MeshBasicMaterial;
      material.opacity = 0.15 + Math.sin(state.clock.elapsedTime * 3) * 0.1;
    }
  });
  return (
    <mesh ref={ref} position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[1.3, 1.5, 48]} />
      <meshBasicMaterial color={color} transparent opacity={isCharging ? 0.25 : 0.12} />
    </mesh>
  );
}

export function CarScene({ colorHex, vehicleClass, batteryPct, isCharging }: CarSceneProps) {
  useCanvasResizeKick();
  return (
    <Canvas camera={{ position: [3, 2, 3.5], fov: 40 }} dpr={[1, 1.5]}>
      <ambientLight intensity={0.7} />
      <directionalLight position={[4, 5, 2]} intensity={1.2} />
      <group rotation={[0, Math.PI / 6, 0]}>
        {vehicleClass === "4W" && <FourWheelCar colorHex={colorHex} />}
        {vehicleClass === "2W" && <TwoWheeler colorHex={colorHex} />}
        {vehicleClass === "3W" && <ThreeWheeler colorHex={colorHex} />}
      </group>
      <ChargeAura batteryPct={batteryPct} isCharging={isCharging} />
      <ContactShadows position={[0, 0, 0]} opacity={0.5} scale={6} blur={2} />
      <OrbitControls enablePan={false} minDistance={2.5} maxDistance={7} maxPolarAngle={Math.PI / 2.1} autoRotate autoRotateSpeed={1.2} />
    </Canvas>
  );
}
