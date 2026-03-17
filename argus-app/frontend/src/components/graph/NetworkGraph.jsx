import { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import * as d3 from 'd3';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

// ═══ THEME COLOR READER — reads CSS custom properties for Canvas rendering ═══
function getThemeColors() {
  const s = getComputedStyle(document.documentElement);
  const get = (name) => s.getPropertyValue(name).trim() || undefined;
  return {
    surface3:   get('--surface-3')   || '#e2e8f0',
    amberBase:  get('--amber-base')  || '#d97706',
    amberTint:  get('--amber-tint')  || '#fef3c7',
    roseBase:   get('--rose-base')   || '#e11d48',
    violetBase: get('--violet-base') || '#7c3aed',
    violetTint: get('--violet-tint') || '#ede9fe',
    accentBase: get('--accent-base') || '#4f46e5',
    text0:      get('--text-0')      || '#0f172a',
    text2:      get('--text-2')      || '#64748b',
    text3:      get('--text-3')      || '#94a3b8',
  };
}

// Cache theme colors — refreshed each simulation setup
let COLORS = getThemeColors();

function nodeRadius(node) {
  switch (node.group) {
    case 'structuring_mule': return 12;
    case 'layering': return 6;
    case 'structuring_source': return 5;
    default: return 3;
  }
}

function nodeColor(node) {
  switch (node.group) {
    case 'structuring_mule': return COLORS.roseBase;
    case 'structuring_source': return COLORS.amberBase;
    case 'layering': return COLORS.violetBase;
    default: return COLORS.surface3;
  }
}

function nodeStroke(node) {
  switch (node.group) {
    case 'structuring_mule': return '#ffffff';
    case 'structuring_source': return COLORS.amberTint;
    case 'layering': return COLORS.violetTint;
    default: return null;
  }
}

function nodeStrokeWidth(node) {
  switch (node.group) {
    case 'structuring_mule': return 2;
    case 'structuring_source': return 1;
    case 'layering': return 1;
    default: return 0;
  }
}

function edgeColor(edge) {
  switch (edge.label) {
    case 'structuring': return COLORS.amberBase;
    case 'layering': return COLORS.violetBase;
    default: return COLORS.surface3;
  }
}

function edgeWidth(edge) {
  switch (edge.label) {
    case 'structuring': return 1.5;
    case 'layering': return 1.5;
    default: return 0.5;
  }
}

function edgeOpacity(edge) {
  switch (edge.label) {
    case 'structuring': return 0.6;
    case 'layering': return 0.6;
    default: return 0.15;
  }
}

const NetworkGraph = forwardRef(function NetworkGraph({ nodes, edges, onNodeSelect, selectedNodeId }, ref) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const simRef = useRef(null);
  const animFrameRef = useRef(null);
  const transformRef = useRef(d3.zoomIdentity);
  const hoveredNodeRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const zoomBehaviorRef = useRef(null);

  // Deep copy nodes/edges so D3 can mutate them
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const quadtreeRef = useRef(null);

  const renderFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width;
    const h = rect.height;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Apply transform
    const t = transformRef.current;
    ctx.setTransform(dpr * t.k, 0, 0, dpr * t.k, dpr * t.x, dpr * t.y);

    const currentEdges = edgesRef.current;
    const currentNodes = nodesRef.current;
    const hovered = hoveredNodeRef.current;

    // ── Draw edges ──
    currentEdges.forEach(edge => {
      if (!edge.source?.x || !edge.target?.x) return;
      ctx.beginPath();
      ctx.moveTo(edge.source.x, edge.source.y);
      ctx.lineTo(edge.target.x, edge.target.y);
      ctx.strokeStyle = edgeColor(edge);
      ctx.lineWidth = edgeWidth(edge) / t.k;
      ctx.globalAlpha = edgeOpacity(edge);
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    // ── Draw nodes ──
    currentNodes.forEach(node => {
      if (node.x == null || node.y == null) return;
      const r = nodeRadius(node);
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = nodeColor(node);
      ctx.fill();

      const stroke = nodeStroke(node);
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = nodeStrokeWidth(node) / t.k;
        ctx.stroke();
      }

      // Mule glow effect
      if (node.group === 'structuring_mule') {
        const pulseR = r + 4 + Math.sin(Date.now() / 300) * 2;
        ctx.beginPath();
        ctx.arc(node.x, node.y, pulseR, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(225, 29, 72, 0.3)';
        ctx.lineWidth = 2 / t.k;
        ctx.stroke();
      }

      // Selected node highlight
      if (String(node.id) === String(selectedNodeId)) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, r + 5, 0, 2 * Math.PI);
        ctx.strokeStyle = COLORS.accentBase;
        ctx.lineWidth = 2.5 / t.k;
        ctx.setLineDash([]);
        ctx.stroke();
      }
    });

    // ── Hover highlight ──
    if (hovered) {
      const r = nodeRadius(hovered);
      ctx.beginPath();
      ctx.arc(hovered.x, hovered.y, r + 6, 0, 2 * Math.PI);
      ctx.strokeStyle = COLORS.accentBase;
      ctx.lineWidth = 2 / t.k;
      ctx.setLineDash([4 / t.k, 4 / t.k]);
      ctx.stroke();
      ctx.setLineDash([]);

      // Highlight connected edges
      currentEdges.forEach(edge => {
        const isConnected =
          (edge.source?.id != null && String(edge.source.id) === String(hovered.id)) ||
          (edge.target?.id != null && String(edge.target.id) === String(hovered.id));
        if (isConnected && edge.source?.x && edge.target?.x) {
          ctx.beginPath();
          ctx.moveTo(edge.source.x, edge.source.y);
          ctx.lineTo(edge.target.x, edge.target.y);
          ctx.strokeStyle = COLORS.accentBase;
          ctx.lineWidth = 2 / t.k;
          ctx.globalAlpha = 0.7;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      });
    }

    ctx.restore();
  }, [selectedNodeId]);

  // ── Setup simulation ──
  useEffect(() => {
    if (!nodes.length || !canvasRef.current) return;

    // Refresh theme colors from CSS custom properties
    COLORS = getThemeColors();

    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    // Deep copy data
    const nodesCopy = nodes.map(n => ({ ...n }));
    const edgesCopy = edges.map(e => ({ ...e, source: e.source, target: e.target }));
    nodesRef.current = nodesCopy;
    edgesRef.current = edgesCopy;

    // Build quadtree for O(log n) spatial hit testing
    const qt = d3.quadtree()
      .x(d => d.x)
      .y(d => d.y)
      .addAll(nodesCopy);
    quadtreeRef.current = qt;

    // Force simulation
    const sim = d3.forceSimulation(nodesCopy)
      .force('link', d3.forceLink(edgesCopy).id(d => d.id).distance(60).strength(0.3))
      .force('charge', d3.forceManyBody().strength(-80).distanceMax(300))
      .force('center', d3.forceCenter(rect.width / 2, rect.height / 2))
      .force('collide', d3.forceCollide().radius(d => nodeRadius(d) + 2))
      .alphaDecay(0.02);

    simRef.current = sim;

    sim.on('tick', () => {
      // Rebuild quadtree as nodes move
      qt.removeAll(nodesCopy).addAll(nodesCopy);
      quadtreeRef.current = qt;
      renderFrame();
    });

    // Animation loop for mule pulse
    function animateLoop() {
      renderFrame();
      animFrameRef.current = requestAnimationFrame(animateLoop);
    }
    // Start animation after simulation cools
    sim.on('end', () => {
      animateLoop();
    });
    // Also start it immediately for mule pulse
    animateLoop();

    // ── Zoom ──
    const zoom = d3.zoom()
      .scaleExtent([0.2, 8])
      .on('zoom', (event) => {
        transformRef.current = event.transform;
        renderFrame();
      });
    zoomBehaviorRef.current = zoom;
    d3.select(canvas).call(zoom);

    // ── Hit testing via quadtree O(log n) ──
    function getNodeAtPoint(mx, my) {
      const t = transformRef.current;
      const x = (mx - t.x) / t.k;
      const y = (my - t.y) / t.k;
      const searchRadius = 20; // max pixel radius to search
      const candidate = qt.find(x, y, searchRadius);
      if (!candidate || candidate.x == null) return null;
      const dx = candidate.x - x;
      const dy = candidate.y - y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const threshold = Math.max(nodeRadius(candidate) + 4, 8);
      return dist <= threshold ? candidate : null;
    }

    // ── Mouse move → hover ──
    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const node = getNodeAtPoint(mx, my);
      hoveredNodeRef.current = node;
      setHoveredNode(node);
      if (node) {
        setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
        canvas.style.cursor = 'pointer';
      } else {
        canvas.style.cursor = 'grab';
      }
    };

    // ── Click → select ──
    const handleClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const node = getNodeAtPoint(mx, my);
      if (node && onNodeSelect) {
        onNodeSelect(String(node.id));
      }
    };

    // ── Double-click → investigate ──
    const handleDblClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const node = getNodeAtPoint(mx, my);
      if (node) {
        window.location.href = `/investigate?subject_id=${node.id}`;
      }
    };

    // ── Drag (using quadtree for subject lookup) ──
    const drag = d3.drag()
      .container(canvas)
      .subject((event) => {
        const t = transformRef.current;
        const x = (event.x - t.x) / t.k;
        const y = (event.y - t.y) / t.k;
        const candidate = qt.find(x, y, 20);
        if (!candidate || candidate.x == null) return null;
        const dx = candidate.x - x;
        const dy = candidate.y - y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        return dist < nodeRadius(candidate) + 8 ? candidate : null;
      })
      .on('start', (event) => {
        if (!event.active) sim.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      })
      .on('drag', (event) => {
        const t = transformRef.current;
        event.subject.fx = (event.x - t.x) / t.k;
        event.subject.fy = (event.y - t.y) / t.k;
      })
      .on('end', (event) => {
        if (!event.active) sim.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      });

    d3.select(canvas).call(drag);

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('click', handleClick);
    canvas.addEventListener('dblclick', handleDblClick);

    // ── Resize handler ──
    const resizeObserver = new ResizeObserver(() => {
      const newRect = canvas.getBoundingClientRect();
      canvas.width = newRect.width * dpr;
      canvas.height = newRect.height * dpr;
      renderFrame();
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      sim.stop();
      cancelAnimationFrame(animFrameRef.current);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('click', handleClick);
      canvas.removeEventListener('dblclick', handleDblClick);
      resizeObserver.disconnect();
    };
  }, [nodes, edges, onNodeSelect, renderFrame]);

  // Expose zoom controls via ref for keyboard shortcuts
  useImperativeHandle(ref, () => ({
    zoomIn: () => handleZoomIn(),
    zoomOut: () => handleZoomOut(),
    fitView: () => handleFitView(),
  }));

  // ── Zoom controls ──
  const handleZoomIn = () => {
    const canvas = canvasRef.current;
    if (!canvas || !zoomBehaviorRef.current) return;
    d3.select(canvas).transition().duration(300).call(zoomBehaviorRef.current.scaleBy, 1.5);
  };
  const handleZoomOut = () => {
    const canvas = canvasRef.current;
    if (!canvas || !zoomBehaviorRef.current) return;
    d3.select(canvas).transition().duration(300).call(zoomBehaviorRef.current.scaleBy, 0.67);
  };
  const handleFitView = () => {
    const canvas = canvasRef.current;
    if (!canvas || !zoomBehaviorRef.current) return;
    d3.select(canvas).transition().duration(500).call(
      zoomBehaviorRef.current.transform,
      d3.zoomIdentity
    );
  };

  return (
    <div ref={containerRef} className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ display: 'block' }}
        role="img"
        aria-label="Interactive financial network graph. Click nodes to select, double-click to investigate. Scroll to zoom, drag to pan."
        tabIndex={0}
      />

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="absolute pointer-events-none z-10 bg-surface-0 border border-surface-3 shadow-md rounded-lg px-3 py-2 text-xs"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 8,
            transform: 'translateY(-100%)',
          }}
        >
          <p className="font-semibold text-text-0">{hoveredNode.name || `Node ${hoveredNode.id}`}</p>
          <p className="text-text-3">{hoveredNode.entity_type} · {hoveredNode.group}</p>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-surface-0/90 backdrop-blur-sm border border-surface-3 rounded-lg p-3 text-xs space-y-1.5">
        {[
          { color: COLORS.surface3, label: 'Legitimate', r: 3 },
          { color: COLORS.amberBase, label: 'Structuring Source', r: 5 },
          { color: COLORS.roseBase, label: 'Mule (Criminal)', r: 8 },
          { color: COLORS.violetBase, label: 'Layering', r: 5 },
        ].map(({ color, label, r }) => (
          <div key={label} className="flex items-center gap-2">
            <svg width={r * 2 + 4} height={r * 2 + 4}>
              <circle cx={r + 2} cy={r + 2} r={r} fill={color} />
            </svg>
            <span className="text-text-2">{label}</span>
          </div>
        ))}
      </div>

      {/* Zoom Controls */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <button
          onClick={handleZoomIn}
          className="p-2 bg-surface-0/90 backdrop-blur-sm border border-surface-3 rounded-lg hover:bg-surface-2 transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4 text-text-2" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-2 bg-surface-0/90 backdrop-blur-sm border border-surface-3 rounded-lg hover:bg-surface-2 transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4 text-text-2" />
        </button>
        <button
          onClick={handleFitView}
          className="p-2 bg-surface-0/90 backdrop-blur-sm border border-surface-3 rounded-lg hover:bg-surface-2 transition-colors"
          title="Fit View"
        >
          <Maximize2 className="w-4 h-4 text-text-2" />
        </button>
      </div>
    </div>
  );
});

export default NetworkGraph;
