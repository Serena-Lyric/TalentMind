// Experimental art parameters, not a production taxonomy, importance or layout model.
export const CONFIG = {
  seed: 261018, radius: 100,
  particles: { dust: 110000, mist: 44000, core: 48000, stars: 10000, field: 2200 },
  spiral: { winding: 4.8, width: 0.19, diskScale: 22, thickness: 2.3 },
  distribution: {
    diffuse: { dust: .12, mist: .35, stars: .06 },
    wingFraction: .18, wingWidth: 2.4, armWander: .16, widthVariation: 1.2,
    warp: 6, densityFloor: .42,
  },
  camera: { distance: 245, min: 24, max: 520, phi: 0.86, theta: 0.18, fov: 43, panRate: 0.32, zoomRate: 0.65 },
  motion: { initial: 0.15, min: 0, max: 2, amplitude: 0.28 },
  render: { dpr: 1.5, bloomStrength: 0.34, bloomRadius: 0.45, bloomThreshold: 0.85, exposure: 1.05 },
  // Profiles: [minimum world size, maximum world size, minimum alpha, maximum alpha].
  appearance: {
    dust: { fine: [.04, .13, .14, .32], haze: [1.2, 2.4, .006, .012], hazeFraction: .05 },
    mist: { haze: [1.8, 3.4, .018, .028], hazeFraction: 1 },
    core: { fine: [.035, .1, .35, .65], haze: [1.8, 2.8, .012, .02], hazeFraction: .14 },
    stars: { fine: [.07, .2, .14, .4], spark: [.3, .55, .5, .8], sparkFraction: .035, hazeFraction: 0 },
    field: { fine: [.11, .32, .14, .24], hazeFraction: 0 },
  },
  hazeResolvePixels: 18, hazeFadeFloor: .55,
  hazeRenderScale: .5,
  maxSprite: { dust: 24, mist: 24, core: 24, stars: 5, field: 3 },
};

export function spiralPoint(radius, branch = 0, offset = 0) {
  const angle = branch * Math.PI / 2 + CONFIG.spiral.winding * (radius / CONFIG.radius) ** .8 + .12 * Math.sin(radius * .09 + branch) + offset;
  return [radius * Math.cos(angle), 0, radius * Math.sin(angle)];
}

export const FAMILIES = [
  { name: '软件研发', color: '#7f9fff', center: spiralPoint(54, 0), spread: 24, examples: ['后端工程师', '分布式系统', 'TypeScript', '企业软件', '服务编排'] },
  { name: '测试与质量工程', color: '#9b88ef', center: spiralPoint(33, 0, .2), spread: 23, examples: ['测试开发工程师', '质量工程', '自动化测试', '软件服务', '回归验证'] },
  { name: '数据与人工智能', color: '#9d8dff', center: spiralPoint(62, 1), spread: 27, examples: ['机器学习工程师', '智能计算', 'PyTorch', '人工智能', '知识检索'] },
  { name: '基础设施与运维', color: '#6bbacf', center: spiralPoint(42, 1, .12), spread: 23, examples: ['平台工程师', '云原生', 'Kubernetes', '云计算', '弹性调度'] },
  { name: '网络与信息安全', color: '#72b8ea', center: spiralPoint(65, 2), spread: 27, examples: ['安全工程师', '网络安全', '零信任', '信息服务', '威胁检测'] },
  { name: '嵌入式与系统软件', color: '#7784e6', center: spiralPoint(37, 2, .12), spread: 24, examples: ['嵌入式工程师', '实时系统', 'C++', '工业控制', '边缘设备'] },
  { name: '技术服务与交付', color: '#6bafcd', center: spiralPoint(59, 3), spread: 27, examples: ['解决方案工程师', '系统交付', '故障诊断', '技术服务', '系统集成'] },
  { name: '硬件与集成电路', color: '#b08ce2', center: spiralPoint(35, 3, .15), spread: 23, examples: ['芯片设计工程师', '数字电路', 'Verilog', '半导体', '芯片验证'] },
];

export const TYPES = [
  { name: '岗位', color: '#b4d6ff', size: 1.15 }, { name: '技术方向', color: '#b4a4ee', size: .95 },
  { name: '技能', color: '#83d9db', size: .8 }, { name: '行业', color: '#d3b2e5', size: .9 },
  { name: '应用场景', color: '#a5bce0', size: .85 },
];
