import { Link, useLocation } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import type { ClientConfig } from "../../config/clientConfig";
import { getTerminology } from "../../config/theme";
import { cn } from "../../lib/utils";

interface BreadcrumbsProps {
  config: ClientConfig;
  className?: string;
}

export function Breadcrumbs({ config, className }: BreadcrumbsProps) {
  const location = useLocation();
  const pathSegments = location.pathname.split("/").filter(Boolean);

  if (pathSegments.length === 0 || location.pathname === "/overview") {
    return (
      <nav
        aria-label="Breadcrumb"
        className={cn("flex items-center text-xs text-muted-foreground", className)}
      >
        <span className="flex items-center font-medium text-foreground">
          <Home className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
          Overview
        </span>
      </nav>
    );
  }

  const resolveSegmentLabel = (segment: string): string => {
    switch (segment) {
      case "staging":
        return `${getTerminology(config, "workbook")} Staging`;
      case "spatial-viewer":
        return `${getTerminology(config, "table")} Spatial Viewer`;
      case "schema-studio":
        return "Schema Studio";
      case "quality-audit":
        return `${getTerminology(config, "defect")} Quality Audit`;
      case "approval-console":
        return `${getTerminology(config, "approval")} Console`;
      case "execution-monitor":
        return `${getTerminology(config, "wal")} Monitor`;
      case "audit-ledger":
        return `${getTerminology(config, "dag")} Audit Ledger`;
      case "settings":
        return "Settings & Customization";
      default:
        return segment.charAt(0).toUpperCase() + segment.slice(1);
    }
  };

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center text-xs text-muted-foreground", className)}
    >
      <ol className="flex items-center space-x-1.5">
        <li>
          <Link
            to="/overview"
            className="flex items-center hover:text-foreground transition-colors"
          >
            <Home className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
            <span>Home</span>
          </Link>
        </li>
        {pathSegments.map((segment, index) => {
          const path = `/${pathSegments.slice(0, index + 1).join("/")}`;
          const isLast = index === pathSegments.length - 1;
          const label = resolveSegmentLabel(segment);

          return (
            <li key={path} className="flex items-center space-x-1.5">
              <ChevronRight className="h-3 w-3 text-muted-foreground/60" aria-hidden="true" />
              {isLast ? (
                <span className="font-semibold text-foreground" aria-current="page">
                  {label}
                </span>
              ) : (
                <Link to={path} className="hover:text-foreground transition-colors">
                  {label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
