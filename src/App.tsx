import React, { useState, useEffect } from 'react';
import { Navigation, TabId } from './components/Navigation';
import { Header } from './components/Header';
import { AgentView } from './views/AgentView';
import { TasksView } from './views/TasksView';
import { DevicesView } from './views/DevicesView';
import { ModelsView } from './views/ModelsView';
import { SettingsView } from './views/SettingsView';
import { FirstRunSetupWizard } from './components/FirstRunSetupWizard';
import { SetupWizardModal } from './components/SetupWizardModal';
import { AgentStatus, SetupStatus } from './types/agent';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('agent');
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatus | null>(null);
  const [isSetupModalOpen, setIsSetupModalOpen] = useState(false);
  const [isCheckingSetup, setIsCheckingSetup] = useState(true);

  const fetchStatus = async () => {
    try {
      const data = await api.getStatus();
      setStatus(data);
    } catch {
      // Python runtime may still be booting or offline
    }
  };

  const checkSetup = async () => {
    try {
      const data = await api.getSetupStatus();
      setSetupStatus(data);
    } catch {
      // ignore transient boot errors
    } finally {
      setIsCheckingSetup(false);
    }
  };

  useEffect(() => {
    checkSetup();
    fetchStatus();
    const interval = setInterval(() => {
      fetchStatus();
      checkSetup();
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  // First-Launch Rule: If setup is not completed, display FirstRunSetupWizard
  const isSetupComplete = setupStatus?.completed === true || setupStatus?.current_state === 'READY';

  if (!isCheckingSetup && setupStatus && !isSetupComplete) {
    return (
      <div className="h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col font-sans antialiased">
        <FirstRunSetupWizard
          onComplete={() => {
            checkSetup();
            fetchStatus();
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 antialiased font-sans">
      {/* Semantic Left Navigation Shell */}
      <Navigation
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isReady={isSetupComplete}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header Bar */}
        <Header
          status={status}
          onOpenSetup={() => setIsSetupModalOpen(true)}
        />

        {/* View Router */}
        <main className="flex-1 overflow-y-auto bg-zinc-950">
          {activeTab === 'agent' && (
            <AgentView
              status={status}
              onRefreshStatus={fetchStatus}
            />
          )}
          {activeTab === 'tasks' && <TasksView />}
          {activeTab === 'devices' && (
            <DevicesView metrics={status?.resource_metrics || null} />
          )}
          {activeTab === 'models' && <ModelsView />}
          {activeTab === 'settings' && (
            <SettingsView onOpenSetup={() => setIsSetupModalOpen(true)} />
          )}
        </main>
      </div>

      {/* Setup Wizard Modal for Recalibration or Diagnostics */}
      {isSetupModalOpen && (
        <FirstRunSetupWizard
          isModal={true}
          onClose={() => setIsSetupModalOpen(false)}
          onComplete={() => {
            setIsSetupModalOpen(false);
            checkSetup();
            fetchStatus();
          }}
        />
      )}
    </div>
  );
}
