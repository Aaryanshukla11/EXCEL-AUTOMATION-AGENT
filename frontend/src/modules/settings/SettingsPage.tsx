import * as React from "react";
import { Download, Palette, RefreshCw, Sliders, Type, Upload } from "lucide-react";
import type { ClientConfig } from "../../config/clientConfig";
import { DEFAULT_CLIENT_CONFIG, validateClientConfig } from "../../config/clientConfig";
import { applyThemeTokens } from "../../config/theme";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";

interface SettingsPageProps {
  config: ClientConfig;
  onUpdateConfig: (updated: ClientConfig) => void;
}

export function SettingsPage({ config, onUpdateConfig }: SettingsPageProps) {
  const [activeTab, setActiveTab] = React.useState<"branding" | "theme" | "terminology" | "io">(
    "theme"
  );
  const [draftConfig, setDraftConfig] = React.useState<ClientConfig>(config);
  const [importError, setImportError] = React.useState<string | null>(null);
  const [importSuccess, setImportSuccess] = React.useState<string | null>(null);

  React.useEffect(() => {
    setDraftConfig(config);
  }, [config]);

  const updateDraft = (updater: (prev: ClientConfig) => ClientConfig) => {
    setDraftConfig((prev) => {
      const next = updater(prev);
      applyThemeTokens(next);
      return next;
    });
  };

  const handleApplyChanges = () => {
    applyThemeTokens(draftConfig);
    onUpdateConfig(draftConfig);
  };

  const handleResetDefaults = () => {
    setDraftConfig(DEFAULT_CLIENT_CONFIG);
    applyThemeTokens(DEFAULT_CLIENT_CONFIG);
    onUpdateConfig(DEFAULT_CLIENT_CONFIG);
  };

  const handleExportJSON = () => {
    const dataStr =
      "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(draftConfig, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "client.config.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportJSON = (e: React.ChangeEvent<HTMLInputElement>) => {
    setImportError(null);
    setImportSuccess(null);
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = JSON.parse(text);
        const res = validateClientConfig(parsed);
        if (!res.isValid) {
          setImportError(res.errors?.join("; ") || "Invalid configuration.");
          return;
        }
        setDraftConfig(res.config);
        applyThemeTokens(res.config);
        onUpdateConfig(res.config);
        setImportSuccess("Configuration successfully validated and applied.");
      } catch (err) {
        setImportError(err instanceof Error ? err.message : "Invalid client.config.json file.");
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Client Customization & Settings Panel
            </h1>
            <Badge variant="outline" className="text-xs">
              Phase F5
            </Badge>
            <Badge variant="default" className="text-xs">
              TIER 1 ZERO-CODE ENGINE
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage enterprise branding, runtime CSS theme tokens, custom terminology, and
            configuration export/import.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm" onClick={handleResetDefaults} className="text-xs h-8">
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
            Reset Defaults
          </Button>
          <Button size="sm" onClick={handleApplyChanges} className="text-xs h-8 font-semibold">
            Apply Changes
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-border pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("theme")}
          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center space-x-1.5 ${
            activeTab === "theme"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          <Palette className="h-3.5 w-3.5" />
          <span>Live Theme & Tokens</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("branding")}
          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center space-x-1.5 ${
            activeTab === "branding"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          <Sliders className="h-3.5 w-3.5" />
          <span>Branding & Identity</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("terminology")}
          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center space-x-1.5 ${
            activeTab === "terminology"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          <Type className="h-3.5 w-3.5" />
          <span>Terminology Overrides</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("io")}
          className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center space-x-1.5 ${
            activeTab === "io"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted"
          }`}
        >
          <Download className="h-3.5 w-3.5" />
          <span>Export / Import JSON</span>
        </button>
      </div>

      {/* Tab 1: Live Theme Customizer */}
      {activeTab === "theme" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Theme Tokens & Color Engine</CardTitle>
              <CardDescription className="text-xs">
                Modifies CSS Custom Properties in real time without recompilation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              {/* Color Scheme */}
              <div>
                <label className="block font-medium text-foreground mb-1">Color Scheme</label>
                <div className="flex items-center space-x-2">
                  {(["light", "dark"] as const).map((scheme) => (
                    <button
                      key={scheme}
                      type="button"
                      onClick={() =>
                        updateDraft((p) => ({
                          ...p,
                          theme: { ...p.theme, colorScheme: scheme },
                        }))
                      }
                      className={`px-3 py-1 text-xs rounded border capitalize font-medium ${
                        draftConfig.theme.colorScheme === scheme
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {scheme}
                    </button>
                  ))}
                </div>
              </div>

              {/* Primary Hue */}
              <div>
                <div className="flex justify-between mb-1">
                  <label className="font-medium text-foreground">
                    Primary Hue ({draftConfig.theme.primaryHue}°)
                  </label>
                  <span className="text-[10px] text-muted-foreground">0° - 360°</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="360"
                  value={draftConfig.theme.primaryHue}
                  onChange={(e) =>
                    updateDraft((p) => ({
                      ...p,
                      theme: { ...p.theme, primaryHue: Number(e.target.value) },
                    }))
                  }
                  className="w-full accent-primary"
                />
              </div>

              {/* Saturation */}
              <div>
                <div className="flex justify-between mb-1">
                  <label className="font-medium text-foreground">
                    Primary Saturation ({draftConfig.theme.primarySaturation}%)
                  </label>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={draftConfig.theme.primarySaturation}
                  onChange={(e) =>
                    updateDraft((p) => ({
                      ...p,
                      theme: { ...p.theme, primarySaturation: Number(e.target.value) },
                    }))
                  }
                  className="w-full accent-primary"
                />
              </div>

              {/* Border Radius */}
              <div>
                <label className="block font-medium text-foreground mb-1">Border Radius</label>
                <div className="flex items-center space-x-2">
                  {(["none", "sm", "md", "lg", "full"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() =>
                        updateDraft((p) => ({
                          ...p,
                          theme: { ...p.theme, borderRadius: r },
                        }))
                      }
                      className={`px-2.5 py-1 text-xs rounded border uppercase font-medium text-[10px] ${
                        draftConfig.theme.borderRadius === r
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Live Preview Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold">Live Visual Preview</CardTitle>
              <CardDescription className="text-xs">
                Real-time preview of buttons, badges, and alerts under current token state.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Button size="sm">Primary Action</Button>
                <Button size="sm" variant="outline">
                  Outline Action
                </Button>
                <Button size="sm" variant="secondary">
                  Secondary
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="default">Primary Badge</Badge>
                <Badge variant="success">Success Status</Badge>
                <Badge variant="warning">Warning Status</Badge>
                <Badge variant="destructive">Critical Error</Badge>
              </div>

              <div className="p-3 rounded-lg border border-border bg-card shadow-sm space-y-1">
                <span className="text-xs font-semibold text-foreground block">
                  Simulated Metric Card
                </span>
                <p className="text-xs text-muted-foreground">
                  The primary hue is currently set to {draftConfig.theme.primaryHue}°.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab 2: Branding & Identity */}
      {activeTab === "branding" && (
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Enterprise Branding</CardTitle>
            <CardDescription className="text-xs">
              Configure application title, organization label, and support contacts.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div>
              <label className="block font-medium text-foreground mb-1">Application Title</label>
              <Input
                value={draftConfig.branding.appTitle}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    branding: { ...p.branding, appTitle: e.target.value },
                  }))
                }
              />
            </div>

            <div>
              <label className="block font-medium text-foreground mb-1">Organization Name</label>
              <Input
                value={draftConfig.branding.organizationName}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    branding: { ...p.branding, organizationName: e.target.value },
                  }))
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tab 3: Terminology Overrides */}
      {activeTab === "terminology" && (
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Domain Terminology Overrides</CardTitle>
            <CardDescription className="text-xs">
              Override default labels with client-specific enterprise terminology.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-medium text-foreground mb-1">Workbook Label</label>
              <Input
                value={draftConfig.terminology.workbook}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    terminology: { ...p.terminology, workbook: e.target.value },
                  }))
                }
              />
            </div>

            <div>
              <label className="block font-medium text-foreground mb-1">Defect Label</label>
              <Input
                value={draftConfig.terminology.defect}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    terminology: { ...p.terminology, defect: e.target.value },
                  }))
                }
              />
            </div>

            <div>
              <label className="block font-medium text-foreground mb-1">Approval Label</label>
              <Input
                value={draftConfig.terminology.approval}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    terminology: { ...p.terminology, approval: e.target.value },
                  }))
                }
              />
            </div>

            <div>
              <label className="block font-medium text-foreground mb-1">WAL Label</label>
              <Input
                value={draftConfig.terminology.wal}
                onChange={(e) =>
                  updateDraft((p) => ({
                    ...p,
                    terminology: { ...p.terminology, wal: e.target.value },
                  }))
                }
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tab 4: Export / Import JSON */}
      {activeTab === "io" && (
        <Card className="max-w-2xl">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Configuration Deployment Engine</CardTitle>
            <CardDescription className="text-xs">
              Download validated{" "}
              <code className="font-mono text-foreground">client.config.json</code> for version
              control or upload an existing client deployment file.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <Button size="sm" onClick={handleExportJSON} className="text-xs">
                <Download className="h-4 w-4 mr-1.5" />
                Export client.config.json
              </Button>

              <label className="cursor-pointer">
                <span className="inline-flex items-center justify-center rounded-md text-xs font-medium border border-input bg-background hover:bg-muted h-9 px-3">
                  <Upload className="h-4 w-4 mr-1.5" />
                  Import client.config.json
                </span>
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={handleImportJSON}
                  className="hidden"
                />
              </label>
            </div>

            {importSuccess && (
              <div className="p-3 rounded bg-success/10 border border-success/30 text-success text-xs">
                {importSuccess}
              </div>
            )}

            {importError && (
              <div className="p-3 rounded bg-destructive/10 border border-destructive/30 text-destructive text-xs">
                Import Error: {importError}
              </div>
            )}

            <div className="font-mono text-[11px] p-3 rounded bg-muted/40 border border-border max-h-60 overflow-y-auto">
              <pre>{JSON.stringify(draftConfig, null, 2)}</pre>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
