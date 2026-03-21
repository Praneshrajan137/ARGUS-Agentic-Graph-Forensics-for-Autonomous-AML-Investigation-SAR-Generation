import { useState, useCallback, useEffect, useRef } from 'react';
import PageHeader from '@/components/shared/PageHeader';
import NetworkGraph from '@/components/graph/NetworkGraph';
import NodeDetailPanel from '@/components/graph/NodeDetailPanel';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ErrorCard from '@/components/shared/ErrorCard';
import { useQuery } from '@/hooks/useQuery';
import { getGraphVisualization } from '@/api/client';

export default function GraphExplorer() {
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const graphRef = useRef(null);
  const { data: graphData, loading, error, refetch } = useQuery(
    'graph-viz', () => getGraphVisualization(5000)
  );

  const handleNodeSelect = useCallback((nodeId) => {
    setSelectedNodeId(nodeId);
  }, []);

  // Keyboard shortcuts: +/= zoom in, - zoom out, 0 fit, Escape deselect
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.key) {
        case '+': case '=':
          graphRef.current?.zoomIn();
          break;
        case '-':
          graphRef.current?.zoomOut();
          break;
        case '0':
          graphRef.current?.fitView();
          break;
        case 'Escape':
          setSelectedNodeId(null);
          break;
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  if (loading) {
    return (
      <div>
        <PageHeader title="Graph Explorer" subtitle="Interactive financial network visualization" />
        <div className="flex items-center justify-center h-[600px] bg-surface-0 rounded-card border border-surface-3">
          <LoadingSpinner size={32} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <PageHeader title="Graph Explorer" subtitle="Interactive financial network visualization" />
        <ErrorCard error={error} onRetry={refetch} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Graph Explorer"
        subtitle={`${graphData?.node_count || graphData?.nodes?.length || 0} entities · ${graphData?.edge_count || graphData?.edges?.length || 0} transactions`}
      />
      <div className="flex gap-0 h-[calc(100vh-180px)] bg-surface-0 rounded-card border border-surface-3 overflow-hidden">
        {/* Graph Canvas */}
        <div className={`relative transition-all duration-300 ${selectedNodeId ? 'w-[60%]' : 'w-full'}`}>
          <NetworkGraph
            ref={graphRef}
            nodes={graphData?.nodes || []}
            edges={graphData?.edges || []}
            onNodeSelect={handleNodeSelect}
            selectedNodeId={selectedNodeId}
          />
        </div>

        {/* Detail Panel */}
        {selectedNodeId && (
          <div className="w-[40%] flex-shrink-0">
            <NodeDetailPanel
              nodeId={selectedNodeId}
              onClose={() => setSelectedNodeId(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
