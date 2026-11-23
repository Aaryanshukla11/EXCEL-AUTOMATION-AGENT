import * as React from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Compass,
  FileCheck,
  Grid,
  LayoutDashboard,
  ShieldAlert,
  Sliders,
  UploadCloud,
  Workflow,
  X,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import type { NavGroupSection, NavItem } from "../../navigation/navigationTypes";
import { cn } from "../../lib/utils";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  UploadCloud,
  Grid,
  Workflow,
  ShieldAlert,
  CheckSquare,
  Activity,
  FileCheck,
  Sliders,
};

export interface SidebarProps extends React.HTMLAttributes<HTMLElement> {
  sections: readonly NavGroupSection[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export function Sidebar({
  className,
  sections,
  isCollapsed,
  onToggleCollapse,
  isMobileOpen,
  onCloseMobile,
  ...props
}: SidebarProps) {
  const renderNavItem = (item: NavItem) => {
    const IconComponent = ICON_MAP[item.iconName] || Compass;
    const isAvailable = item.status === "ready";

    return (
      <NavLink
        key={item.id}
        to={item.path}
        onClick={onCloseMobile}
        className={({ isActive }) =>
          cn(
            "group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors relative",
            isActive
              ? "bg-primary/10 text-primary font-semibold"
              : "text-muted-foreground hover:bg-muted hover:text-foreground",
            !isAvailable && "opacity-75",
            isCollapsed && "justify-center px-2"
          )
        }
      >
        <IconComponent className={cn("h-4 w-4 flex-shrink-0", !isCollapsed && "mr-3")} />
        {!isCollapsed && <span className="flex-1 truncate">{item.label}</span>}
        {!isCollapsed && item.badge && (
          <Badge
            variant={item.status === "ready" ? "success" : "outline"}
            className="ml-auto text-[10px] px-1.5 py-0 font-normal uppercase"
          >
            {item.badge}
          </Badge>
        )}
      </NavLink>
    );
  };

  return (
    <>
      {/* Mobile Drawer & Overlay (only rendered when open) */}
      {isMobileOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden animate-in fade-in"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-72 bg-card border-r border-border md:hidden transform transition-transform duration-200 ease-in-out">
            <div className="flex flex-col h-full">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <span className="text-sm font-semibold text-foreground">Navigation</span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onCloseMobile}
                  aria-label="Close navigation"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
                {sections.map((section) => (
                  <div key={section.group} className="space-y-1">
                    <h4 className="px-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                      {section.title}
                    </h4>
                    <div className="space-y-0.5">{section.items.map(renderNavItem)}</div>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </>
      )}

      {/* Desktop Persistent Sidebar */}
      <aside
        className={cn(
          "hidden md:flex flex-col border-r border-border bg-card transition-all duration-200 flex-shrink-0",
          isCollapsed ? "w-16" : "w-64",
          className
        )}
        {...props}
      >
        <div className="flex flex-col h-full">
          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
            {sections.map((section) => (
              <div key={section.group} className="space-y-1">
                {!isCollapsed && (
                  <h4 className="px-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                    {section.title}
                  </h4>
                )}
                <div className="space-y-0.5">{section.items.map(renderNavItem)}</div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-end p-3 border-t border-border">
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleCollapse}
              className="w-full flex items-center justify-center text-muted-foreground hover:text-foreground"
              aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {isCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <>
                  <ChevronLeft className="h-4 w-4 mr-2" />
                  <span className="text-xs">Collapse</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
}
