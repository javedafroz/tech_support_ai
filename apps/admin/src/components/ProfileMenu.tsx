import { useEffect, useState } from "react";
import Badge from "./Badge";

export type ProfileUser = {
  subject: string;
  username: string | null;
  email: string | null;
  roles: string[];
};

type Props = {
  me: ProfileUser | null;
  onSignOut: () => void;
};

function initials(me: ProfileUser): string {
  const source = me.username || me.email || me.subject || "?";
  const parts = source.split(/[@.\s_-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export default function ProfileMenu({ me, onSignOut }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!me) return null;

  const displayName = me.username || me.email || me.subject || "Admin";
  const kbRoles = me.roles.filter((r) => r.startsWith("kb_"));

  return (
    <div className="profile-menu">
      <button
        type="button"
        className="avatar-btn"
        aria-label="Open profile menu"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="avatar">{initials(me)}</span>
      </button>

      {open ? (
        <>
          <div
            className="profile-backdrop"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div className="profile-popover" role="dialog" aria-label="Profile settings">
            <div className="profile-popover-header">
              <span className="avatar avatar-lg">{initials(me)}</span>
              <div className="profile-popover-meta">
                <div className="profile-popover-name">{displayName}</div>
                {me.email ? <div className="profile-popover-email">{me.email}</div> : null}
              </div>
            </div>

            {kbRoles.length > 0 ? (
              <div className="profile-popover-roles">
                {kbRoles.map((role) => (
                  <Badge key={role} variant="neutral">
                    {role}
                  </Badge>
                ))}
              </div>
            ) : null}

            <div className="profile-popover-divider" />

            <button
              type="button"
              className="btn secondary"
              style={{ width: "100%" }}
              onClick={() => {
                setOpen(false);
                onSignOut();
              }}
            >
              Sign out
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
