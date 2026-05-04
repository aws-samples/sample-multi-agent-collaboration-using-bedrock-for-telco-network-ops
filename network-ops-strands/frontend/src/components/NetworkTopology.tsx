import React, { useEffect, useRef, useState } from 'react';
import { Network } from 'vis-network';
import { api } from '../services/api';

interface INetworkNode {
  id: string;
  label: string;
  group: string;
  x: number;
  y: number;
  details: Record<string, any>;
}

interface INetworkEdge {
  from: string;
  to: string;
  label: string;
}

interface ITopologyData {
  nodes: INetworkNode[];
  edges: INetworkEdge[];
  profile: string;
}

interface INetworkTopologyProps {
  profile?: string;
}

export const NetworkTopology: React.FC<INetworkTopologyProps> = ({ profile = 'datacenter' }) => {
  const networkContainer = useRef<HTMLDivElement>(null);
  const networkInstance = useRef<Network | null>(null);
  const [topology, setTopology] = useState<ITopologyData | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<INetworkNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTopology();
  }, [profile]);

  useEffect(() => {
    if (topology && networkContainer.current) {
      initializeNetwork();
    }
    return () => {
      if (networkInstance.current) {
        networkInstance.current.destroy();
      }
    };
  }, [topology]);

  const loadTopology = async () => {
    try {
      setLoading(true);
      const data = await api.getTopology(profile);
      setTopology(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load topology:', err);
      setError('Failed to load network topology');
    } finally {
      setLoading(false);
    }
  };

  const initializeNetwork = () => {
    if (!topology || !networkContainer.current) return;

    // Define color schemes for different node groups
    const colorSchemes = {
      datacenter: {
        core: { background: '#DC2626', border: '#991B1B', font: { color: '#FFFFFF' } },
        distribution: { background: '#EA580C', border: '#C2410C', font: { color: '#FFFFFF' } },
        access: { background: '#CA8A04', border: '#A16207', font: { color: '#FFFFFF' } },
        compute: { background: '#2563EB', border: '#1E40AF', font: { color: '#FFFFFF' } },
        storage: { background: '#7C3AED', border: '#5B21B6', font: { color: '#FFFFFF' } },
        security: { background: '#059669', border: '#047857', font: { color: '#FFFFFF' } }
      },
      telco: {
        core: { background: '#DC2626', border: '#991B1B', font: { color: '#FFFFFF' } },
        ran: { background: '#2563EB', border: '#1E40AF', font: { color: '#FFFFFF' } },
        small_cell: { background: '#7C3AED', border: '#5B21B6', font: { color: '#FFFFFF' } }
      }
    };

    const colors = (colorSchemes as Record<string, Record<string, unknown>>)[profile] || colorSchemes.datacenter;

    // Alarm color overrides
    const alarmColors = {
      critical: { background: '#DC2626', border: '#7F1D1D', font: { color: '#FFFFFF' } },
      major: { background: '#F97316', border: '#C2410C', font: { color: '#FFFFFF' } },
      minor: { background: '#FACC15', border: '#CA8A04', font: { color: '#000000' } }
    };

    // Prepare nodes for vis-network
    const nodes = topology.nodes.map(node => {
      let nodeColor = colors[node.group as keyof typeof colors] || { background: '#6B7280', border: '#4B5563' };
      
      // Override color if node has alarm
      if (node.details.status === 'alarm' && node.details.alarm_severity) {
        nodeColor = alarmColors[node.details.alarm_severity as keyof typeof alarmColors] || nodeColor;
      }

      return {
        id: node.id,
        label: node.label,
        x: node.x,
        y: node.y,
        color: nodeColor,
        shape: 'box',
        font: { size: 12, face: 'Inter, sans-serif' },
        margin: { top: 10, right: 10, bottom: 10, left: 10 },
        borderWidth: node.details.status === 'alarm' ? 4 : 2,
        shadow: node.details.status === 'alarm' ? { enabled: true, size: 15, color: 'rgba(220, 38, 38, 0.5)' } : true,
        scaling: {
          min: 10,
          max: 30,
          label: {
            enabled: true,
            min: 12,
            max: 16
          }
        }
      };
    });

    // Prepare edges for vis-network
    const edges = topology.edges.map(edge => ({
      from: edge.from,
      to: edge.to,
      label: edge.label,
      font: { size: 10, align: 'middle' },
      color: { color: '#94A3B8', highlight: '#3B82F6' },
      width: 2,
      smooth: { enabled: true, type: 'cubicBezier', roundness: 0.5 }
    }));

    const data = { nodes, edges };

    const options = {
      physics: {
        enabled: false // Fixed layout
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true,
        selectConnectedEdges: false
      },
      nodes: {
        shape: 'box',
        font: {
          size: 12,
          face: 'Inter, sans-serif'
        },
        chosen: {
          node: (values: any, _id: string, selected: boolean, _hovering: boolean) => {
            if (selected) {
              values.borderWidth = 6;
              values.shadow = true;
              values.shadowSize = 25;
              values.shadowColor = 'rgba(59, 130, 246, 0.6)';
              values.size = 30;
            }
          }
        }
      },
      edges: {
        font: {
          size: 10,
          align: 'middle'
        },
        smooth: {
          type: 'cubicBezier'
        },
        chosen: {
          edge: (values: any, _id: string, selected: boolean, _hovering: boolean) => {
            if (selected) {
              values.width = 4;
              values.color = '#3B82F6';
            }
          }
        }
      }
    };

    networkInstance.current = new Network(networkContainer.current, data, options as any);

    // Handle node selection
    networkInstance.current.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = topology.nodes.find(n => n.id === nodeId);
        if (node) {
          setSelectedDevice(node);
          
          // Highlight connected edges
          const connectedEdges = networkInstance.current?.getConnectedEdges(nodeId);
          if (connectedEdges && networkInstance.current) {
            networkInstance.current.selectEdges(connectedEdges);
          }
        }
      } else {
        setSelectedDevice(null);
      }
    });

    // Add hover effect
    networkInstance.current.on('hoverNode', (_params) => {
      if (networkContainer.current) {
        networkContainer.current.style.cursor = 'pointer';
      }
    });

    networkInstance.current.on('blurNode', (_params) => {
      if (networkContainer.current) {
        networkContainer.current.style.cursor = 'default';
      }
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500 dark:text-gray-400">Loading network topology...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-slate-50 dark:bg-slate-900">
      {/* Network Graph */}
      <div className="flex-1 relative">
        {/* Header Controls */}
        <div className="absolute top-4 left-4 z-10 space-y-3">
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 border border-slate-200 dark:border-slate-700">
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 mb-2">
              {'Data Center Network'}
            </h2>
            <button
              onClick={loadTopology}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm font-medium w-full"
            >
              🔄 Refresh Network
            </button>
          </div>

          {/* Alarm Summary */}
          {topology && (() => {
            const alarmNodes = topology.nodes.filter(n => n.details.status === 'alarm');
            const criticalCount = alarmNodes.filter(n => n.details.alarm_severity === 'critical').length;
            const majorCount = alarmNodes.filter(n => n.details.alarm_severity === 'major').length;
            const minorCount = alarmNodes.filter(n => n.details.alarm_severity === 'minor').length;
            
            if (alarmNodes.length > 0) {
              return (
                <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-3 flex items-center gap-2">
                    <span className="text-red-500">⚠️</span>
                    Active Alarms ({alarmNodes.length})
                  </h3>
                  <div className="space-y-2 text-xs">
                    {criticalCount > 0 && (
                      <div className="flex items-center justify-between p-2 bg-red-50 dark:bg-red-900/20 rounded">
                        <span className="text-red-700 dark:text-red-400 font-medium">Critical</span>
                        <span className="font-bold text-red-700 dark:text-red-400">{criticalCount}</span>
                      </div>
                    )}
                    {majorCount > 0 && (
                      <div className="flex items-center justify-between p-2 bg-orange-50 dark:bg-orange-900/20 rounded">
                        <span className="text-orange-700 dark:text-orange-400 font-medium">Major</span>
                        <span className="font-bold text-orange-700 dark:text-orange-400">{majorCount}</span>
                      </div>
                    )}
                    {minorCount > 0 && (
                      <div className="flex items-center justify-between p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded">
                        <span className="text-yellow-700 dark:text-yellow-400 font-medium">Minor</span>
                        <span className="font-bold text-yellow-700 dark:text-yellow-400">{minorCount}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            }
            return null;
          })()}

          {/* Legend */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg p-4 border border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-3">Legend</h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 rounded border-2 border-green-700"></div>
                <span className="text-slate-700 dark:text-slate-300">Online</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-600 rounded border-4 border-red-800"></div>
                <span className="text-slate-700 dark:text-slate-300">Critical Alarm</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-orange-500 rounded border-4 border-orange-700"></div>
                <span className="text-slate-700 dark:text-slate-300">Major Alarm</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-yellow-400 rounded border-4 border-yellow-600"></div>
                <span className="text-slate-700 dark:text-slate-300">Minor Alarm</span>
              </div>
            </div>
          </div>
        </div>
        <div ref={networkContainer} className="w-full h-full" />
      </div>

      {/* Device Details Panel */}
      {selectedDevice && (
        <div className="w-96 bg-white dark:bg-slate-800 border-l border-slate-200 dark:border-slate-700 overflow-y-auto">
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                  {selectedDevice.details.type}
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                  {selectedDevice.id}
                </p>
              </div>
              <button
                onClick={() => setSelectedDevice(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            {/* Status Indicator */}
            {selectedDevice.details.status === 'alarm' ? (
              <div className="mb-6">
                <div className={`flex items-center gap-2 p-3 rounded-lg mb-3 ${
                  selectedDevice.details.alarm_severity === 'critical' 
                    ? 'bg-red-50 dark:bg-red-900/20' 
                    : selectedDevice.details.alarm_severity === 'major'
                    ? 'bg-orange-50 dark:bg-orange-900/20'
                    : 'bg-yellow-50 dark:bg-yellow-900/20'
                }`}>
                  <div className={`w-3 h-3 rounded-full animate-pulse ${
                    selectedDevice.details.alarm_severity === 'critical'
                      ? 'bg-red-500'
                      : selectedDevice.details.alarm_severity === 'major'
                      ? 'bg-orange-500'
                      : 'bg-yellow-500'
                  }`} />
                  <span className={`text-sm font-bold uppercase ${
                    selectedDevice.details.alarm_severity === 'critical'
                      ? 'text-red-700 dark:text-red-400'
                      : selectedDevice.details.alarm_severity === 'major'
                      ? 'text-orange-700 dark:text-orange-400'
                      : 'text-yellow-700 dark:text-yellow-400'
                  }`}>
                    {selectedDevice.details.alarm_severity} Alarm
                  </span>
                </div>
                
                {/* Alarm Details */}
                <div className="p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg border-l-4 border-red-500">
                  <div className="mb-2">
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      Alarm Type
                    </span>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100 mt-1">
                      {selectedDevice.details.alarm_type?.replace(/_/g, ' ')}
                    </p>
                  </div>
                  <div className="mb-2">
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      Started
                    </span>
                    <p className="text-sm text-slate-900 dark:text-slate-100 mt-1">
                      {selectedDevice.details.alarm_start}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      Reason
                    </span>
                    <p className="text-sm text-slate-900 dark:text-slate-100 mt-1 leading-relaxed">
                      {selectedDevice.details.alarm_reason}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 mb-6 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                <span className="text-sm font-medium text-green-700 dark:text-green-400">
                  {selectedDevice.details.status || 'Online'}
                </span>
              </div>
            )}

            {/* Device Details */}
            <div className="space-y-4">
              {Object.entries(selectedDevice.details).map(([key, value]) => {
                // Skip these fields as they're displayed elsewhere
                if (key === 'type' || key === 'status' || key === 'alarm_severity' || 
                    key === 'alarm_reason' || key === 'alarm_type' || key === 'alarm_start') {
                  return null;
                }
                
                const label = key.split('_').map(word => 
                  word.charAt(0).toUpperCase() + word.slice(1)
                ).join(' ');

                return (
                  <div key={key} className="border-b border-slate-200 dark:border-slate-700 pb-3">
                    <dt className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                      {label}
                    </dt>
                    <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100 font-medium">
                      {value}
                    </dd>
                  </div>
                );
              })}
            </div>

            {/* Metrics (if available) */}
            {(selectedDevice.details.cpu_utilization || selectedDevice.details.memory_utilization) && (
              <div className="mt-6 p-4 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 mb-3">
                  Resource Utilization
                </h4>
                {selectedDevice.details.cpu_utilization && (
                  <div className="mb-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-600 dark:text-slate-400">CPU</span>
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {selectedDevice.details.cpu_utilization}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${selectedDevice.details.cpu_utilization}%` }}
                      />
                    </div>
                  </div>
                )}
                {selectedDevice.details.memory_utilization && (
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-600 dark:text-slate-400">Memory</span>
                      <span className="font-medium text-slate-900 dark:text-slate-100">
                        {selectedDevice.details.memory_utilization}%
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-2">
                      <div
                        className="bg-purple-500 h-2 rounded-full transition-all"
                        style={{ width: `${selectedDevice.details.memory_utilization}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
