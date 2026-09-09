"""
Componente de Visualização 3D Interativa do Motor.

Renderiza um motor elétrico procedural em Three.js (WebGL) embutido via
`streamlit.components.v1.html`. O modelo reage em tempo real aos dados de
telemetria do ativo selecionado:

- Velocidade de rotação do eixo/hélice  -> proporcional ao RPM
- Cor do corpo do motor                 -> Status (Normal / Alerta / Crítico)
- Intensidade da vibração visual        -> valor de Vibração (mm/s)
- Brilho/emissão térmica das aletas     -> Temperatura (°C)

O usuário pode arrastar com o mouse para orbitar a câmera e usar o
scroll para dar zoom (OrbitControls).
"""

import json
import streamlit.components.v1 as components

# Paleta de cores por status de saúde do ativo
_CORES_STATUS = {
    "Normal": {"corpo": "#2ecc71", "emissivo": "#0e5c2a", "glow": "#2ecc71"},
    "Alerta": {"corpo": "#f1c40f", "emissivo": "#7a5c00", "glow": "#f1c40f"},
    "Crítico": {"corpo": "#e74c3c", "emissivo": "#7a1a10", "glow": "#e74c3c"},
}


def render_motor_engine_3d(
    status: str = "Normal",
    rpm: float = 0.0,
    vibracao: float = 0.0,
    temperatura: float = 25.0,
    corrente: float = 0.0,
    motor_tag: str = "",
    height: int = 480,
):
    """
    Renderiza o motor 3D interativo dentro do app Streamlit.

    Parâmetros:
        status:       "Normal" | "Alerta" | "Crítico"
        rpm:          rotação atual do motor (afeta velocidade de giro)
        vibracao:     valor de vibração em mm/s (afeta o "shake" visual)
        temperatura:  temperatura em °C (afeta o brilho/glow das aletas)
        corrente:     corrente em A (exibida no HUD dentro da cena)
        motor_tag:    identificador do ativo (exibido no HUD)
        height:       altura em pixels do canvas 3D
    """
    cores = _CORES_STATUS.get(status, _CORES_STATUS["Normal"])

    # Normalizações defensivas (evita crash se vier None/str do banco)
    try:
        rpm_val = float(rpm) if rpm is not None else 0.0
    except (TypeError, ValueError):
        rpm_val = 0.0
    try:
        vib_val = float(vibracao) if vibracao is not None else 0.0
    except (TypeError, ValueError):
        vib_val = 0.0
    try:
        temp_val = float(temperatura) if temperatura is not None else 25.0
    except (TypeError, ValueError):
        temp_val = 25.0
    try:
        corrente_val = float(corrente) if corrente is not None else 0.0
    except (TypeError, ValueError):
        corrente_val = 0.0

    config = {
        "status": status,
        "rpm": rpm_val,
        "vibracao": vib_val,
        "temperatura": temp_val,
        "corrente": corrente_val,
        "motorTag": motor_tag,
        "corCorpo": cores["corpo"],
        "corEmissivo": cores["emissivo"],
        "corGlow": cores["glow"],
    }
    config_json = json.dumps(config)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body {{
    margin: 0; padding: 0; overflow: hidden;
    background: radial-gradient(circle at 50% 30%, #1a1f2e 0%, #0a0c12 100%);
    border-radius: 12px;
  }}
  #canvas-container {{ width: 100%; height: {height}px; position: relative; }}
  #hud {{
    position: absolute; top: 12px; left: 14px;
    font-family: 'Segoe UI', Arial, sans-serif; color: #e8ecf1;
    font-size: 13px; line-height: 1.5; pointer-events: none;
    background: rgba(15, 18, 28, 0.55); padding: 10px 14px;
    border-radius: 10px; backdrop-filter: blur(4px);
    border: 1px solid rgba(255,255,255,0.08);
  }}
  #hud b {{ font-size: 14px; }}
  #status-badge {{
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-weight: 600; font-size: 12px; margin-top: 4px;
  }}
  #hint {{
    position: absolute; bottom: 10px; right: 14px;
    font-family: 'Segoe UI', Arial, sans-serif; color: #8a93a6;
    font-size: 11px; pointer-events: none;
  }}
</style>
</head>
<body>
<div id="canvas-container">
  <div id="hud">
    <b>⚙️ {motor_tag or "Ativo"}</b><br/>
    RPM: <span id="hud-rpm">--</span><br/>
    Vibração: <span id="hud-vib">--</span> mm/s<br/>
    Temperatura: <span id="hud-temp">--</span>°C<br/>
    Corrente: <span id="hud-corrente">--</span> A<br/>
    <span id="status-badge">--</span>
  </div>
  <div id="hint">🖱️ arraste para girar · scroll para zoom</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const CFG = {config_json};

// ---- Preenche HUD ----
document.getElementById('hud-rpm').textContent = CFG.rpm.toFixed(0);
document.getElementById('hud-vib').textContent = CFG.vibracao.toFixed(2);
document.getElementById('hud-temp').textContent = CFG.temperatura.toFixed(1);
document.getElementById('hud-corrente').textContent = CFG.corrente.toFixed(2);
const badge = document.getElementById('status-badge');
badge.textContent = CFG.status;
badge.style.background = CFG.corGlow;
badge.style.color = (CFG.status === 'Alerta') ? '#3a2f00' : '#ffffff';

// ---- OrbitControls minimalista (sem depender de CDN extra) ----
function MiniOrbitControls(camera, domElement) {{
  this.camera = camera;
  this.domElement = domElement;
  this.radius = 9;
  this.theta = Math.PI / 4;   // horizontal
  this.phi = Math.PI / 2.6;   // vertical
  this.target = new THREE.Vector3(0, 0.3, 0);
  this.isDragging = false;
  this.prev = {{ x: 0, y: 0 }};

  const self = this;

  domElement.addEventListener('mousedown', (e) => {{
    self.isDragging = true;
    self.prev.x = e.clientX;
    self.prev.y = e.clientY;
  }});
  window.addEventListener('mouseup', () => {{ self.isDragging = false; }});
  window.addEventListener('mousemove', (e) => {{
    if (!self.isDragging) return;
    const dx = e.clientX - self.prev.x;
    const dy = e.clientY - self.prev.y;
    self.theta -= dx * 0.008;
    self.phi -= dy * 0.008;
    self.phi = Math.max(0.35, Math.min(Math.PI - 0.35, self.phi));
    self.prev.x = e.clientX;
    self.prev.y = e.clientY;
  }});
  domElement.addEventListener('wheel', (e) => {{
    e.preventDefault();
    self.radius += e.deltaY * 0.01;
    self.radius = Math.max(4, Math.min(20, self.radius));
  }}, {{ passive: false }});

  // Touch support (mobile)
  domElement.addEventListener('touchstart', (e) => {{
    self.isDragging = true;
    self.prev.x = e.touches[0].clientX;
    self.prev.y = e.touches[0].clientY;
  }}, {{ passive: true }});
  window.addEventListener('touchend', () => {{ self.isDragging = false; }});
  window.addEventListener('touchmove', (e) => {{
    if (!self.isDragging) return;
    const dx = e.touches[0].clientX - self.prev.x;
    const dy = e.touches[0].clientY - self.prev.y;
    self.theta -= dx * 0.008;
    self.phi -= dy * 0.008;
    self.phi = Math.max(0.35, Math.min(Math.PI - 0.35, self.phi));
    self.prev.x = e.touches[0].clientX;
    self.prev.y = e.touches[0].clientY;
  }}, {{ passive: true }});

  this.update = function () {{
    const x = self.target.x + self.radius * Math.sin(self.phi) * Math.cos(self.theta);
    const y = self.target.y + self.radius * Math.cos(self.phi);
    const z = self.target.z + self.radius * Math.sin(self.phi) * Math.sin(self.theta);
    self.camera.position.set(x, y, z);
    self.camera.lookAt(self.target);
  }};
}}

// ---- Cena ----
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();

const camera = new THREE.PerspectiveCamera(45, container.clientWidth / {height}, 0.1, 100);
const controls = new MiniOrbitControls(camera, container);

const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
renderer.setSize(container.clientWidth, {height});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
container.appendChild(renderer.domElement);

// Luzes
scene.add(new THREE.AmbientLight(0x8899aa, 0.6));
const key = new THREE.DirectionalLight(0xffffff, 1.1);
key.position.set(5, 8, 5);
scene.add(key);
const rim = new THREE.PointLight(new THREE.Color(CFG.corGlow), 1.4, 15);
rim.position.set(-3, 2, -3);
scene.add(rim);

// Chão levemente refletivo (fake) só para dar contexto de "piso de fábrica"
const chao = new THREE.Mesh(
  new THREE.CircleGeometry(6, 48),
  new THREE.MeshStandardMaterial({{ color: 0x14171f, roughness: 0.85, metalness: 0.2 }})
);
chao.rotation.x = -Math.PI / 2;
chao.position.y = -1.35;
scene.add(chao);

// Grupo do motor inteiro (para aplicar vibração no grupo todo)
const motorGroup = new THREE.Group();
scene.add(motorGroup);

const matCorpo = new THREE.MeshStandardMaterial({{
  color: new THREE.Color(CFG.corCorpo),
  emissive: new THREE.Color(CFG.corEmissivo),
  emissiveIntensity: 0.35 + Math.min(CFG.temperatura / 200, 0.6),
  metalness: 0.55,
  roughness: 0.35,
}});
const matMetal = new THREE.MeshStandardMaterial({{ color: 0x9aa3ad, metalness: 0.85, roughness: 0.3 }});
const matEscuro = new THREE.MeshStandardMaterial({{ color: 0x22252b, metalness: 0.6, roughness: 0.5 }});

// Corpo principal (carcaça cilíndrica do motor)
const corpo = new THREE.Mesh(new THREE.CylinderGeometry(1.15, 1.15, 2.4, 32), matCorpo);
corpo.rotation.z = Math.PI / 2;
motorGroup.add(corpo);

// Aletas de refrigeração (radiais ao longo do corpo)
const aletaGeo = new THREE.BoxGeometry(2.42, 0.08, 0.22);
for (let i = 0; i < 14; i++) {{
  const aleta = new THREE.Mesh(aletaGeo, matCorpo);
  const ang = (i / 14) * Math.PI * 2;
  aleta.position.set(0, Math.cos(ang) * 1.22, Math.sin(ang) * 1.22);
  aleta.rotation.x = ang;
  motorGroup.add(aleta);
}}

// Caixa de terminais (lateral)
const caixa = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.55, 0.55), matEscuro);
caixa.position.set(0, 1.35, 0);
motorGroup.add(caixa);

// Tampas frontal/traseira (flanges)
const flangeGeo = new THREE.CylinderGeometry(1.28, 1.28, 0.18, 32);
const flangeFrente = new THREE.Mesh(flangeGeo, matMetal);
flangeFrente.rotation.z = Math.PI / 2;
flangeFrente.position.x = 1.29;
motorGroup.add(flangeFrente);
const flangeTras = flangeFrente.clone();
flangeTras.position.x = -1.29;
motorGroup.add(flangeTras);

// Pés de fixação
const peGeo = new THREE.BoxGeometry(0.35, 0.25, 2.6);
const pe1 = new THREE.Mesh(peGeo, matEscuro);
pe1.position.set(0, -1.15, 0);
motorGroup.add(pe1);

// Grupo do eixo giratório (eixo + hélice de ventilação)
const eixoGroup = new THREE.Group();
motorGroup.add(eixoGroup);

const eixo = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 3.0, 24), matMetal);
eixo.rotation.z = Math.PI / 2;
eixoGroup.add(eixo);

// Hélice/ventoinha na ponta traseira
const heliceGroup = new THREE.Group();
heliceGroup.position.x = -1.55;
for (let i = 0; i < 6; i++) {{
  const pa = new THREE.Mesh(
    new THREE.BoxGeometry(0.05, 0.55, 0.14),
    matMetal
  );
  pa.rotation.x = (i / 6) * Math.PI * 2;
  pa.position.y = 0;
  heliceGroup.add(pa);
}}
const cuboHelice = new THREE.Mesh(new THREE.SphereGeometry(0.18, 16, 16), matEscuro);
heliceGroup.add(cuboHelice);
eixoGroup.add(heliceGroup);

// Ponta do eixo saindo pela frente (acoplamento)
const pontaEixo = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.6, 16), matMetal);
pontaEixo.rotation.z = Math.PI / 2;
pontaEixo.position.x = 1.6;
eixoGroup.add(pontaEixo);

// Halo de "glow" no chão sob o motor, cor = status
const halo = new THREE.Mesh(
  new THREE.RingGeometry(1.4, 2.6, 48),
  new THREE.MeshBasicMaterial({{ color: new THREE.Color(CFG.corGlow), transparent: true, opacity: 0.25, side: THREE.DoubleSide }})
);
halo.rotation.x = -Math.PI / 2;
halo.position.y = -1.34;
scene.add(halo);

// ---- Animação ----
// Velocidade angular do eixo proporcional ao RPM (escala visual, não literal)
const velocidadeEixo = Math.min(CFG.rpm / 300, 8.0); // rad/s aproximado, limitado p/ não "estroboscopiar"
// Intensidade da vibração (shake) proporcional ao valor de vibração
const intensidadeVibracao = Math.min(CFG.vibracao * 0.015, 0.12);

const clock = new THREE.Clock();

function animate() {{
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  eixoGroup.rotation.x += velocidadeEixo * clock.getDelta ? 0 : 0; // no-op guard
  eixoGroup.rotation.x = t * velocidadeEixo;

  if (intensidadeVibracao > 0.0005) {{
    motorGroup.position.y = Math.sin(t * 40) * intensidadeVibracao;
    motorGroup.position.z = Math.cos(t * 37) * intensidadeVibracao * 0.6;
  }}

  // Pulsar sutil do halo (respiração) — mais rápido se Crítico
  const pulseSpeed = CFG.status === 'Crítico' ? 6 : (CFG.status === 'Alerta' ? 3 : 1.2);
  halo.material.opacity = 0.18 + Math.abs(Math.sin(t * pulseSpeed)) * 0.18;
  rim.intensity = 1.1 + Math.abs(Math.sin(t * pulseSpeed)) * 0.6;

  controls.update();
  renderer.render(scene, camera);
}}
animate();

// Responsivo
window.addEventListener('resize', () => {{
  const w = container.clientWidth;
  camera.aspect = w / {height};
  camera.updateProjectionMatrix();
  renderer.setSize(w, {height});
}});
</script>
</body>
</html>
"""
    components.html(html, height=height + 10, scrolling=False)