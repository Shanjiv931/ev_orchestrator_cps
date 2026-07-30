import { useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const vertexShader = `
  void main() {
    gl_Position = vec4( position, 1.0 );
  }
`;

const fragmentShader = `
  precision highp float;
  uniform vec2 resolution;
  uniform float time;

  // Computes one color channel's contribution. The original wrote this as
  // color[j] += ... with j as the outer loop variable - dynamically
  // indexing a vec3 with a non-constant index is a known-flaky GLSL
  // pattern on some driver/ANGLE toolchains (seen here as a "potentially
  // uninitialized variable" compiler warning immediately followed by
  // WebGL context loss) - unrolled into three explicit calls instead,
  // identical math, no dynamic vector indexing.
  float channel(vec2 uv, float t, float phase) {
    float lineWidth = 0.002;
    float value = 0.0;
    for (int i = 0; i < 5; i++) {
      value += lineWidth*float(i*i) / abs(fract(t - phase + float(i)*0.01)*5.0 - length(uv) + mod(uv.x+uv.y, 0.2));
    }
    return value;
  }

  void main(void) {
    vec2 uv = (gl_FragCoord.xy * 2.0 - resolution.xy) / min(resolution.x, resolution.y);
    float t = time*0.05;

    vec3 color = vec3(channel(uv, t, 0.0), channel(uv, t, 0.01), channel(uv, t, 0.02));

    // dialed back so the raw RGB shader reads as ambient energy behind the
    // globe rather than a competing full-strength visual against the
    // brand's own emerald/cyan palette
    gl_FragColor = vec4(color, 0.35);
  }
`;

// The vertex shader deliberately ignores modelViewMatrix/projectionMatrix -
// it outputs `position` straight to clip space, the classic full-viewport
// quad trick. That's what lets this render correctly as a background layer
// no matter what camera the rest of the R3F scene (the globe/particles in
// IntroScene) is using, without needing a second orthographic camera or,
// more importantly, a second WebGL context: a separate vanilla-three.js
// renderer stacked on top of R3F's own was hitting "Context Lost" under
// combined GPU load, so this renders inside the existing <Canvas> instead.
export function ShaderBackground() {
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const { size, gl } = useThree();

  useFrame(() => {
    const material = materialRef.current;
    if (!material) return;
    material.uniforms.time.value += 0.05;
    const pixelRatio = gl.getPixelRatio();
    material.uniforms.resolution.value.set(size.width * pixelRatio, size.height * pixelRatio);
  });

  return (
    <mesh renderOrder={-1} frustumCulled={false}>
      <planeGeometry args={[2, 2]} />
      <shaderMaterial
        ref={materialRef}
        uniforms={{ time: { value: 1.0 }, resolution: { value: new THREE.Vector2() } }}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        transparent
        depthTest={false}
        depthWrite={false}
      />
    </mesh>
  );
}
