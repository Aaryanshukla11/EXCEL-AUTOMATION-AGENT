import * as React from "react";
import { BrowserRouter } from "react-router-dom";
import { LayoutProvider } from "../components/layout/LayoutProvider";
import { AppRoutes } from "../routes/AppRoutes";
import { DEFAULT_CLIENT_CONFIG, type ClientConfig } from "../config/clientConfig";
import { applyThemeTokens } from "../config/theme";

export interface AppProps {
  initialConfig?: ClientConfig;
}

export function App({ initialConfig }: AppProps) {
  const [config, setConfig] = React.useState<ClientConfig>(initialConfig || DEFAULT_CLIENT_CONFIG);

  // Initialize runtime theme CSS variables
  React.useEffect(() => {
    applyThemeTokens(config);
  }, [config]);

  const toggleTheme = () => {
    setConfig((prev) => {
      const nextScheme: "light" | "dark" = prev.theme.colorScheme === "dark" ? "light" : "dark";
      const updated: ClientConfig = {
        ...prev,
        theme: {
          ...prev.theme,
          colorScheme: nextScheme,
        },
      };
      applyThemeTokens(updated);
      return updated;
    });
  };

  return (
    <BrowserRouter>
      <LayoutProvider config={config} onToggleTheme={toggleTheme}>
        <AppRoutes config={config} onUpdateConfig={setConfig} />
      </LayoutProvider>
    </BrowserRouter>
  );
}
