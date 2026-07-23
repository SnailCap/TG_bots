import { useCallback, useState } from "react";

import type { ProjectSettings, StudioApiClient } from "../../studio/api";

export function useProjectSettings(api: StudioApiClient, projectId: string) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [projectSettings, setProjectSettings] = useState<ProjectSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState("");

  const loadProjectSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError("");
    try {
      setProjectSettings(await api.getProjectSettings(projectId));
    } catch (caught) {
      setSettingsError(caught instanceof Error ? caught.message : "Could not load project settings.");
    } finally {
      setSettingsLoading(false);
    }
  }, [api, projectId]);

  const openProjectSettings = useCallback(() => {
    setSettingsOpen(true);
    void loadProjectSettings();
  }, [loadProjectSettings]);

  const saveProjectSettings = useCallback(async (telegramBotToken: string) => {
    if (!projectSettings) throw new Error(settingsError || "Project settings are still loading.");
    setSettingsSaving(true);
    try {
      const next = await api.saveProjectSettings(projectId, {
        telegram_bot_token: telegramBotToken,
        revision: projectSettings.revision,
      });
      setProjectSettings(next);
      setSettingsError("");
    } finally {
      setSettingsSaving(false);
    }
  }, [api, projectId, projectSettings, settingsError]);

  const clearProjectSettings = useCallback(async () => {
    if (!projectSettings) throw new Error("Project settings are still loading.");
    setSettingsSaving(true);
    try {
      const next = await api.saveProjectSettings(projectId, {
        clear_telegram_bot_token: true,
        revision: projectSettings.revision,
      });
      setProjectSettings(next);
      setSettingsError("");
    } finally {
      setSettingsSaving(false);
    }
  }, [api, projectId, projectSettings]);

  return {
    settingsOpen,
    setSettingsOpen,
    projectSettings,
    settingsLoading,
    settingsSaving,
    openProjectSettings,
    saveProjectSettings,
    clearProjectSettings,
  };
}
