import { motion, AnimatePresence } from 'framer-motion';
import { X, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import TypologyBadge from '@/components/shared/TypologyBadge';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { useQuery } from '@/hooks/useQuery';
import { getNode, getNodeTransactions, getNodeConnections } from '@/api/client';

export default function NodeDetailPanel({ nodeId, onClose }) {
  const { data: node, loading: nodeLoading } = useQuery(
    `node-${nodeId}`, () => getNode(nodeId), { enabled: !!nodeId }
  );
  const { data: txData, loading: txLoading } = useQuery(
    `node-tx-${nodeId}`, () => getNodeTransactions(nodeId), { enabled: !!nodeId }
  );
  const { data: connData } = useQuery(
    `node-conn-${nodeId}`, () => getNodeConnections(nodeId), { enabled: !!nodeId }
  );

  const transactions = Array.isArray(txData) ? txData : (txData?.transactions ?? []);
  const connections = Array.isArray(connData) ? connData : (connData?.connections ?? []);

  return (
    <AnimatePresence>
      {nodeId && (
        <motion.div
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="w-full h-full bg-surface-0 border-l border-surface-3 overflow-y-auto"
        >
          {nodeLoading ? (
            <div className="flex items-center justify-center h-full">
              <LoadingSpinner size={28} />
            </div>
          ) : node ? (
            <>
              {/* Header */}
              <div className="p-5 border-b border-surface-3">
                <div className="flex items-center justify-between mb-2">
                  <h2 className="font-display text-lg text-text-0 truncate">{node.name || `Entity ${node.id}`}</h2>
                  <button
                    onClick={onClose}
                    className="p-1 rounded hover:bg-surface-2 transition-colors"
                  >
                    <X className="w-4 h-4 text-text-3" />
                  </button>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs text-text-3">ID: {node.id}</span>
                  {node.is_criminal && <TypologyBadge typology={node.crime_type?.toUpperCase()} />}
                </div>
              </div>

              {/* KYC Data Grid */}
              <div className="p-5 border-b border-surface-3 grid grid-cols-2 gap-4">
                {[
                  ['Entity Type', node.entity_type],
                  ['Jurisdiction', node.jurisdiction],
                  ['Risk Rating', node.risk_rating],
                  ['Degree', `${node.degree ?? '—'} (in: ${node.in_degree ?? '—'}, out: ${node.out_degree ?? '—'})`],
                  ['SWIFT', node.swift_code || '—'],
                  ['IFSC', node.ifsc_code || '—'],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-[11px] font-medium text-text-3 uppercase tracking-wider mb-0.5">{label}</p>
                    <p className="text-sm font-mono text-text-0">{value}</p>
                  </div>
                ))}
              </div>

              {/* Transaction Table */}
              <div className="p-5 border-b border-surface-3">
                <h3 className="text-sm font-semibold text-text-1 mb-3">
                  Recent Transactions
                  {!txLoading && Array.isArray(transactions) && (
                    <span className="text-text-3 font-normal ml-1">({transactions.length})</span>
                  )}
                </h3>
                {txLoading ? (
                  <div className="flex justify-center py-4">
                    <LoadingSpinner size={20} />
                  </div>
                ) : Array.isArray(transactions) && transactions.length > 0 ? (
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {transactions.slice(0, 20).map((tx, idx) => (
                      <div key={tx.id || idx} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-1 text-xs">
                        <div className="truncate">
                          <span className="font-mono text-text-0">{tx.source}</span>
                          <span className="text-text-3 mx-1.5">→</span>
                          <span className="font-mono text-text-0">{tx.target}</span>
                        </div>
                        <div className="text-right flex-shrink-0 ml-2">
                          <span className={`font-mono font-medium ${
                            tx.label === 'structuring' ? 'text-status-amber' :
                            tx.label === 'layering' ? 'text-status-violet' : 'text-text-1'
                          }`}>
                            ${Number(tx.amount).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-text-3 text-center py-4">No transactions found</p>
                )}
              </div>

              {/* Connections Summary */}
              {Array.isArray(connections) && connections.length > 0 && (
                <div className="p-5 border-b border-surface-3">
                  <h3 className="text-sm font-semibold text-text-1 mb-3">
                    Connections <span className="text-text-3 font-normal">({connections.length})</span>
                  </h3>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {connections.slice(0, 15).map((conn, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs p-2 rounded bg-surface-1">
                        <span className="font-mono text-text-0 truncate">{conn.name || `Node ${conn.id}`}</span>
                        <span className="text-text-3">{conn.entity_type}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="p-5">
                <Link
                  to={`/investigate?subject_id=${node.id}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-white text-sm font-semibold rounded-btn hover:bg-accent-hover transition-colors"
                >
                  <Search className="w-4 h-4" /> Investigate Entity
                </Link>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-text-3 text-sm">
              Node not found
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
