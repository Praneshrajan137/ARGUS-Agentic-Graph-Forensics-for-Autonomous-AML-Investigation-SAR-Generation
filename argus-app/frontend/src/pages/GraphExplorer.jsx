import { useState, useCallback } from 'react';
import PageHeader from '@/components/shared/PageHeader';
import NetworkGraph from '@/components/graph/NetworkGraph';
import NodeDetailPanel from '@/components/graph/NodeDetailPanel';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import ErrorCard from '@/components/shared/ErrorCard';
import { useQuery } from '@/hooks/useQuery';
import { getGraphVisualization } from '@/api/client';

export default function GraphExplorer() {
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const { data: graphData, loading, error, refetch } = useQuery(
    'graph-viz', () => getGraphVisualization(500)
  );

  const handleNodeSelect = useCallback((nodeId) => {
    setSelectedNodeId(nodeId);
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
