import * as React from "react";
import { Bell, Menu, Moon, Sun, User } from "lucide-react";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/DropdownMenu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/Dialog";
import type { ClientConfig } from "../../config/clientConfig";
import { cn } from "../../lib/utils";

export interface HeaderProps extends React.HTMLAttributes<HTMLElement> {
  config: ClientConfig;
  onToggleTheme?: () => void;
  onToggleMobileNav?: () => void;
}

export function Header({
  className,
  config,
  onToggleTheme,
  onToggleMobileNav,
  ...props
}: HeaderProps) {
  const { branding, theme } = config;

  return (
    <header
      className={cn(
        "sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-border bg-background/95 px-4 sm:px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        className
      )}
      {...props}
    >
      {/* Brand & Mobile Hamburger */}
      <div className="flex items-center space-x-3">
        {onToggleMobileNav && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleMobileNav}
            className="md:hidden"
            aria-label="Toggle navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}

        <div className="flex items-center space-x-3">
          {branding.logoUrl ? (
            <img src={branding.logoUrl} alt={branding.organizationName} className="h-8 w-auto" />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded bg-primary font-bold text-primary-foreground text-sm shadow-sm">
              EI
            </div>
          )}
          <div className="flex flex-col">
            <span className="font-semibold text-sm leading-tight text-foreground">
              {branding.appTitle}
            </span>
            <span className="text-xs text-muted-foreground hidden sm:inline">
              {branding.organizationName}
            </span>
          </div>
        </div>
      </div>

      {/* Header Actions (Theme, Notifications, Profile) */}
      <div className="flex items-center space-x-2">
        {/* Theme Toggle */}
        {onToggleTheme && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleTheme}
            aria-label="Toggle theme"
            title="Toggle color theme"
          >
            {theme.colorScheme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
        )}

        {/* Notifications Area Placeholder */}
        <Dialog>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label="View notifications"
              title="Notifications"
            >
              <Bell className="h-4 w-4" />
              <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-primary" />
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Platform Notifications</DialogTitle>
              <DialogDescription>
                System events and pending audit alerts for {branding.organizationName}.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div className="rounded border p-3 text-xs bg-muted/40">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-semibold text-foreground">Engine Initialized</span>
                  <Badge variant="outline">Telemetry</Badge>
                </div>
                <p className="text-muted-foreground">
                  F0 Foundation & F1 Application Shell loaded in strict client-config mode.
                </p>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* User / Profile Menu Placeholder */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="flex items-center space-x-2 pl-2 pr-3"
              aria-label="User profile menu"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
                <User className="h-4 w-4" />
              </div>
              <span className="text-xs font-medium hidden md:inline">Admin User</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col space-y-0.5">
                <span className="font-semibold text-sm">Enterprise Administrator</span>
                <span className="text-xs text-muted-foreground">{branding.organizationName}</span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem>Session Telemetry</DropdownMenuItem>
              <DropdownMenuItem>Switch Organization</DropdownMenuItem>
              <DropdownMenuItem>Client Config Inspector</DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">
              Sign Out (Local Session)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
