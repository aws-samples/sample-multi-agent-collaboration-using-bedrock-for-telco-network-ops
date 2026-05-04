import React, { useEffect, useState, useRef } from 'react';
import { AlertTriangle, Wrench, Radio, Zap, BarChart3, CloudSun } from 'lucide-react';
import { api } from '../services/api';
import type { IDashboardMetrics } from '../types';

interface IDashboardProps {
  onNavigateToChat: (query: string, autoSend?: boolean) => void;
}

export const Dashboard: React.FC<IDashboardProps> = ({ onNavigateToChat }) => {
  const [metrics, setMetrics] = useState<IDashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchedRef = useRef(false);

  useEffect(() => {
    if (!fetchedRef.current) {
      fetchedRef.current = true;
      loadMetrics();
    }
  }, []);

  const loadMetrics = async () => {
    try {
      setLoading(true);
      console.log('📊 Dashboard: Fetching metrics...');
      const data = await api.getDashboardMetrics();
      console.log('📊 Dashboard: Received data:', data);
      console.log('📊 Dashboard: Active alarms:', data.activeAlarms);
      console.log('📊 Dashboard: Ongoing maintenance:', data.ongoingMaintenance);
      setMetrics(data);
      setError(null);
    } catch (err) {
      console.error('❌ Dashboard: Error loading metrics:', err);
      setError('Failed to load metrics');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500 dark:text-gray-400">Loading metrics...</div>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">{error || 'No metrics available'}</div>
      </div>
    );
  }

  const totalAlarms = 
    (metrics.activeAlarms?.critical || 0) +
    (metrics.activeAlarms?.major || 0) +
    (metrics.activeAlarms?.minor || 0) +
    (metrics.activeAlarms?.warning || 0);

  console.log('📊 Dashboard: Rendering with metrics:', {
    totalAlarms,
    critical: metrics.activeAlarms?.critical,
    major: metrics.activeAlarms?.major,
    minor: metrics.activeAlarms?.minor,
    ongoingMaintenance: metrics.ongoingMaintenance,
    sitesMonitored: metrics.sitesMonitored,
    averageLatency: metrics.averageLatency
  });

  return (
    <div className="p-8 space-y-8 bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-100 mb-2">
          Network Operations Dashboard
        </h1>
        <p className="text-slate-600 dark:text-slate-400">
          Real-time monitoring and insights for your network infrastructure
        </p>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Active Alarms */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Active Alarms</p>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {totalAlarms}
              </p>
            </div>
            <div className="w-14 h-14 rounded-xl bg-red-100 dark:bg-red-900/20 flex items-center justify-center">
              <AlertTriangle className="w-7 h-7 text-red-600 dark:text-red-400" />
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between items-center p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <span className="text-red-700 dark:text-red-400 font-medium">Critical</span>
              <span className="font-bold text-red-700 dark:text-red-400">{metrics.activeAlarms?.critical || 0}</span>
            </div>
            <div className="flex justify-between items-center p-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
              <span className="text-orange-700 dark:text-orange-400 font-medium">Major</span>
              <span className="font-bold text-orange-700 dark:text-orange-400">{metrics.activeAlarms?.major || 0}</span>
            </div>
            <div className="flex justify-between items-center p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
              <span className="text-yellow-700 dark:text-yellow-400 font-medium">Minor</span>
              <span className="font-bold text-yellow-700 dark:text-yellow-400">{metrics.activeAlarms?.minor || 0}</span>
            </div>
          </div>
        </div>

        {/* Ongoing Maintenance */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Ongoing Maintenance</p>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {metrics.ongoingMaintenance || 0}
              </p>
            </div>
            <div className="w-14 h-14 rounded-xl bg-emerald-100 dark:bg-emerald-900/20 flex items-center justify-center">
              <Wrench className="w-7 h-7 text-emerald-600 dark:text-emerald-400" />
            </div>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-700/50 p-3 rounded-lg">
            Active maintenance windows across all sites
          </p>
        </div>

        {/* Sites Monitored */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Sites Monitored</p>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {metrics.sitesMonitored || 0}
              </p>
            </div>
            <div className="w-14 h-14 rounded-xl bg-indigo-100 dark:bg-indigo-900/20 flex items-center justify-center">
              <Radio className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
            </div>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-700/50 p-3 rounded-lg">
            Distributed across multiple locations
          </p>
        </div>

        {/* Average Latency */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 hover:shadow-xl transition-all duration-300 hover:scale-[1.02]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">Avg Latency</p>
              <p className="text-4xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {(metrics.averageLatency || 0).toFixed(1)}<span className="text-2xl text-slate-500">ms</span>
              </p>
            </div>
            <div className="w-14 h-14 rounded-xl bg-amber-100 dark:bg-amber-900/20 flex items-center justify-center">
              <Zap className="w-7 h-7 text-amber-600 dark:text-amber-400" />
            </div>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-700/50 p-3 rounded-lg">
            Network response time performance
          </p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="max-w-7xl mx-auto bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-8 border border-slate-200 dark:border-slate-700">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-6 flex items-center gap-3">
          <Zap className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
          <span>Quick Actions</span>
        </h2>

        {/* Auto-send: Generic queries that apply to all sites */}
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">Instant Queries</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <button 
            onClick={() => onNavigateToChat('Show all active alarms across all sites', true)}
            className="group px-5 py-4 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-xl hover:from-red-600 hover:to-red-700 transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <AlertTriangle className="w-5 h-5" />
            <span className="font-semibold text-sm">View All Alarms</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('Show all ongoing and upcoming maintenance across all sites', true)}
            className="group px-5 py-4 bg-gradient-to-r from-emerald-500 to-emerald-600 text-white rounded-xl hover:from-emerald-600 hover:to-emerald-700 transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <Wrench className="w-5 h-5" />
            <span className="font-semibold text-sm">All Maintenance</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('Which sites have both active alarms and scheduled maintenance?', true)}
            className="group px-5 py-4 bg-gradient-to-r from-rose-500 to-rose-600 text-white rounded-xl hover:from-rose-600 hover:to-rose-700 transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <AlertTriangle className="w-5 h-5" />
            <span className="font-semibold text-sm">Alarms + Maintenance</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('Are there any anomalies in the network performance today?', true)}
            className="group px-5 py-4 bg-gradient-to-r from-teal-500 to-teal-600 text-white rounded-xl hover:from-teal-600 hover:to-teal-700 transition-all duration-300 shadow-md hover:shadow-lg transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <Zap className="w-5 h-5" />
            <span className="font-semibold text-sm">Detect Anomalies</span>
          </button>
        </div>

        {/* Prefill: Site-specific queries the user can customize */}
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">Site-Specific (edit site before sending)</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <button 
            onClick={() => onNavigateToChat('Analyze KPIs for site_atlanta_001')}
            className="group px-5 py-4 bg-white dark:bg-slate-700 border-2 border-indigo-200 dark:border-indigo-800 text-slate-800 dark:text-slate-200 rounded-xl hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-all duration-300 shadow-sm hover:shadow-md transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <BarChart3 className="w-5 h-5 text-indigo-500" />
            <span className="font-semibold text-sm">Analyze Performance</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('Give me a full report on site_dallas_003 including maintenance, alarms, and performance')}
            className="group px-5 py-4 bg-white dark:bg-slate-700 border-2 border-amber-200 dark:border-amber-800 text-slate-800 dark:text-slate-200 rounded-xl hover:border-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-all duration-300 shadow-sm hover:shadow-md transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <Radio className="w-5 h-5 text-amber-500" />
            <span className="font-semibold text-sm">Full Site Report</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('Plot a bar chart comparing throughput across all Dallas and Atlanta sites')}
            className="group px-5 py-4 bg-white dark:bg-slate-700 border-2 border-violet-200 dark:border-violet-800 text-slate-800 dark:text-slate-200 rounded-xl hover:border-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 transition-all duration-300 shadow-sm hover:shadow-md transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <BarChart3 className="w-5 h-5 text-violet-500" />
            <span className="font-semibold text-sm">Throughput Chart</span>
          </button>
          <button 
            onClick={() => onNavigateToChat('What is the weather in Dallas and are there any power outages near site_dallas_003?')}
            className="group px-5 py-4 bg-white dark:bg-slate-700 border-2 border-sky-200 dark:border-sky-800 text-slate-800 dark:text-slate-200 rounded-xl hover:border-sky-400 hover:bg-sky-50 dark:hover:bg-sky-900/20 transition-all duration-300 shadow-sm hover:shadow-md transform hover:-translate-y-1 flex items-center justify-center gap-3"
          >
            <CloudSun className="w-5 h-5 text-sky-500" />
            <span className="font-semibold text-sm">Weather & Outages</span>
          </button>
        </div>
      </div>
    </div>
  );
};
