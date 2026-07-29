import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown, LockKeyhole, RotateCcw, Search, UsersRound, X } from "lucide-react";

import { ResizeHandle } from "../../shared/ui/ResizeHandle";
import { ConfirmationDialog } from "../../shared/ui/ConfirmationDialog";
import { Select, type SelectOption } from "../../shared/ui/Select";
import type { ManagedUser, StudioApiClient, UserRole, UserStatus } from "../../studio/api";

export type BotUser = ManagedUser;

type SortKey = "user" | "role" | "status";
type SortDirection = "asc" | "desc";

const ROLE_LABELS: Record<UserRole, string> = {
  user: "User",
  trusted: "Trusted user",
  moderator: "Moderator",
  administrator: "Administrator",
};

const STATUS_LABELS: Record<UserStatus, string> = {
  active: "Active",
  blocked: "Blocked",
};

const ROLE_OPTIONS: SelectOption[] = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS: SelectOption[] = Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }));
const ALL_OPTION: SelectOption = { value: "all", label: "All" };
const USER_DETAILS_WIDTH_KEY = "tg-bot-studio.users.details-width";
const USER_DETAILS_DEFAULT_WIDTH = 372;
const USER_DETAILS_MIN_WIDTH = 310;
const USER_DETAILS_MAX_WIDTH = 620;

interface UsersPageProps {
  api?: Pick<StudioApiClient, "listUsers" | "updateUser">;
  apiBaseUrl?: string;
  projectId?: string;
  initialUsers?: readonly BotUser[];
  hidden?: boolean;
}

export function UsersPage({ api, apiBaseUrl = "", projectId, initialUsers, hidden = false }: UsersPageProps) {
  const [users, setUsers] = useState<BotUser[]>(() => initialUsers?.map(copyUser) ?? []);
  const [loading, setLoading] = useState(initialUsers === undefined);
  const [loadRevision, setLoadRevision] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({ key: "user", direction: "asc" });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [focusedUserId, setFocusedUserId] = useState<string | null>(null);
  const [detailsClosing, setDetailsClosing] = useState(false);
  const [detailsWidth, setDetailsWidth] = useState(loadUserDetailsWidth);
  const [bulkRole, setBulkRole] = useState("");
  const [bulkStatus, setBulkStatus] = useState("");
  const [notice, setNotice] = useState("");
  const detailsWidthRef = useRef(detailsWidth);

  useEffect(() => {
    if (initialUsers !== undefined) {
      setUsers(initialUsers.map(copyUser));
      setLoading(false);
      return undefined;
    }
    if (!api || !projectId) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    void api.listUsers(projectId)
      .then((loaded) => {
        if (!cancelled) setUsers(loaded.map(copyUser));
      })
      .catch((caught: unknown) => {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not load users.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [api, initialUsers, loadRevision, projectId]);

  const closeUserDetails = useCallback(() => {
    if (focusedUserId && !detailsClosing) setDetailsClosing(true);
  }, [detailsClosing, focusedUserId]);

  const finishClosingUserDetails = useCallback(() => {
    if (!detailsClosing) return;
    setFocusedUserId(null);
    setDetailsClosing(false);
  }, [detailsClosing]);

  useEffect(() => {
    if (!focusedUserId) return undefined;
    const closeDetails = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeUserDetails();
    };
    window.addEventListener("keydown", closeDetails);
    return () => window.removeEventListener("keydown", closeDetails);
  }, [closeUserDetails, focusedUserId]);

  useEffect(() => {
    const clampToViewport = () => {
      const nextWidth = clampUserDetailsWidth(detailsWidthRef.current);
      if (nextWidth === detailsWidthRef.current) return;
      detailsWidthRef.current = nextWidth;
      setDetailsWidth(nextWidth);
    };
    window.addEventListener("resize", clampToViewport);
    return () => window.removeEventListener("resize", clampToViewport);
  }, []);

  const filteredUsers = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLocaleLowerCase();
    return users
      .filter((user) => {
        if (normalizedQuery && !`${displayName(user)} ${user.username ?? ""} ${user.telegramId}`.toLocaleLowerCase().includes(normalizedQuery)) return false;
        if (roleFilter !== "all" && user.role !== roleFilter) return false;
        return statusFilter === "all" || user.status === statusFilter;
      })
      .slice()
      .sort((left, right) => compareUsers(left, right, sort));
  }, [deferredQuery, roleFilter, sort, statusFilter, users]);

  const focusedUser = users.find((user) => user.telegramId === focusedUserId) ?? null;
  const visibleIds = filteredUsers.map((user) => user.telegramId);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const hasFilters = Boolean(query || roleFilter !== "all" || statusFilter !== "all");

  const persistUsers = async (changed: readonly BotUser[]) => {
    setSaving(true);
    setError("");
    try {
      const saved = api && projectId
        ? await Promise.all(changed.map((user) => api.updateUser(projectId, user.telegramId, {
          role: user.role,
          blocked: user.status === "blocked",
          note: user.note,
        })))
        : changed;
      const byId = new Map(saved.map((user) => [user.telegramId, user]));
      setUsers((current) => current.map((user) => byId.get(user.telegramId) ?? user));
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save user changes.");
      return false;
    } finally {
      setSaving(false);
    }
  };
  const openUser = (id: string) => {
    setDetailsClosing(false);
    setFocusedUserId(id);
  };
  const setDetailsSize = useCallback((width: number) => {
    detailsWidthRef.current = width;
    setDetailsWidth(width);
  }, []);
  const commitDetailsSize = useCallback(() => saveUserDetailsWidth(detailsWidthRef.current), []);
  const openUserFromKeyboard = (event: KeyboardEvent<HTMLTableRowElement>, id: string) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    openUser(id);
  };
  const toggleSelected = (id: string) => setSelectedIds((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const toggleAllVisible = () => setSelectedIds((current) => {
    const next = new Set(current);
    if (allVisibleSelected) visibleIds.forEach((id) => next.delete(id)); else visibleIds.forEach((id) => next.add(id));
    return next;
  });
  const changeSort = (key: SortKey) => setSort((current) => current.key === key
    ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
    : { key, direction: "asc" });
  const clearFilters = () => {
    setQuery("");
    setRoleFilter("all");
    setStatusFilter("all");
  };
  const applyBulkChanges = async () => {
    if (!selectedIds.size || (!bulkRole && !bulkStatus)) return;
    const changed = users
      .filter((user) => selectedIds.has(user.telegramId))
      .map((user) => ({
        ...user,
        role: (bulkRole || user.role) as UserRole,
        status: (bulkStatus || user.status) as UserStatus,
      }));
    if (!await persistUsers(changed)) return;
    setNotice(`Updated ${changed.length} ${changed.length === 1 ? "user" : "users"}.`);
    setBulkRole("");
    setBulkStatus("");
  };

  return <section className="users-page" aria-label="User management" hidden={hidden}>
    <div className="users-page__body">
      <div className="users-manager" inert={focusedUser ? true : undefined}>
        <div className="users-toolbar">
          <label className="users-search">
            <span className="sr-only">Search users</span><SearchIcon />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, username, or Telegram ID" />
            {query && <button type="button" aria-label="Clear search" onClick={() => setQuery("")}><CloseIcon /></button>}
          </label>
          <FilterControl label="Role"><Select value={roleFilter} options={[ALL_OPTION, ...ROLE_OPTIONS]} ariaLabel="Filter by role" onChange={setRoleFilter} /></FilterControl>
          <FilterControl label="Status"><Select value={statusFilter} options={[ALL_OPTION, ...STATUS_OPTIONS]} ariaLabel="Filter by status" onChange={setStatusFilter} /></FilterControl>
        </div>

        {error && <div className="users-page__error" role="alert">{error}</div>}
        {selectedIds.size > 0 && <div className="users-bulk-bar" role="region" aria-label="Bulk user actions">
          <div className="users-bulk-bar__count"><span>{selectedIds.size}</span> selected</div>
          <div className="users-bulk-bar__field"><Select value={bulkRole} placeholder="Set role" options={ROLE_OPTIONS} ariaLabel="Bulk role" onChange={setBulkRole} /></div>
          <div className="users-bulk-bar__field"><Select value={bulkStatus} placeholder="Set status" options={STATUS_OPTIONS} ariaLabel="Bulk status" onChange={setBulkStatus} /></div>
          <button type="button" className="users-bulk-bar__apply" disabled={saving || (!bulkRole && !bulkStatus)} onClick={() => void applyBulkChanges()}>{saving ? "Saving…" : "Apply changes"}</button>
          <button type="button" className="users-bulk-bar__clear" onClick={() => setSelectedIds(new Set())}>Clear</button>
        </div>}

        <div className="users-table-shell">
          {loading ? null : error && users.length === 0 ? <LoadErrorState onRetry={() => setLoadRevision((value) => value + 1)} /> : users.length === 0 ? <EmptyUsersState /> : filteredUsers.length === 0 ? <NoResultsState onClear={clearFilters} /> : <>
            <div className="users-table__scroll"><table className="users-table">
              <thead><tr>
                <th className="users-table__check"><input type="checkbox" aria-label="Select all visible users" checked={allVisibleSelected} onChange={toggleAllVisible} /></th>
                <SortableHeader label="User" sortKey="user" sort={sort} onSort={changeSort} />
                <SortableHeader label="Role" sortKey="role" sort={sort} onSort={changeSort} />
                <SortableHeader label="Status" sortKey="status" sort={sort} onSort={changeSort} />
              </tr></thead>
              <tbody>{filteredUsers.map((user) => <UserRow key={user.telegramId} user={user} avatarUrl={userAvatarUrl(apiBaseUrl, projectId, user)} selected={selectedIds.has(user.telegramId)} focused={focusedUserId === user.telegramId} onOpen={() => openUser(user.telegramId)} onOpenFromKeyboard={(event) => openUserFromKeyboard(event, user.telegramId)} onToggle={(event) => { event.stopPropagation(); toggleSelected(user.telegramId); }} />)}</tbody>
            </table></div>
            <footer className="users-table__footer"><span>Showing {filteredUsers.length} of {users.length} users</span><span>Click a row to view details</span></footer>
          </>}
        </div>
      </div>

      {focusedUser && <div className={detailsClosing ? "user-details-layer user-details-layer--closing" : "user-details-layer"} data-testid="user-details-backdrop" onPointerDown={(event) => { if (event.target === event.currentTarget) closeUserDetails(); }}>
        <UserDetails
          user={focusedUser}
          avatarUrl={userAvatarUrl(apiBaseUrl, projectId, focusedUser)}
          closing={detailsClosing}
          saving={saving}
          width={detailsWidth}
          onClose={closeUserDetails}
          onClosed={finishClosingUserDetails}
          onResize={setDetailsSize}
          onResizeEnd={commitDetailsSize}
          onSave={async (changed) => {
            if (await persistUsers([changed])) setNotice("User details updated.");
          }}
        />
      </div>}
    </div>
    {notice && <div className="users-page__notice" role="status">{notice}<button type="button" aria-label="Dismiss notification" onClick={() => setNotice("")}><CloseIcon /></button></div>}
  </section>;
}

function UserRow({ user, avatarUrl, selected, focused, onOpen, onOpenFromKeyboard, onToggle }: { user: BotUser; avatarUrl?: string; selected: boolean; focused: boolean; onOpen(): void; onOpenFromKeyboard(event: KeyboardEvent<HTMLTableRowElement>): void; onToggle(event: MouseEvent<HTMLInputElement>): void }) {
  const name = displayName(user);
  return <tr className={focused ? "users-table__row users-table__row--focused" : "users-table__row"} tabIndex={0} aria-label={`Open ${name}`} onClick={onOpen} onKeyDown={onOpenFromKeyboard}>
    <td className="users-table__check"><input type="checkbox" aria-label={`Select ${name}`} checked={selected} onClick={onToggle} onChange={() => undefined} /></td>
    <td><div className="user-identity"><Avatar user={user} imageUrl={avatarUrl} /><span><strong>{name}</strong>{user.username && <small>@{user.username}</small>}</span></div></td>
    <td><span className={`access-label access-label--${user.role}`}>{ROLE_LABELS[user.role]}</span></td>
    <td><StatusBadge status={user.status} /></td>
  </tr>;
}

function UserDetails({ user, avatarUrl, closing, saving, width, onClose, onClosed, onResize, onResizeEnd, onSave }: {
  user: BotUser; avatarUrl?: string; closing: boolean; saving: boolean; width: number;
  onClose(): void; onClosed(): void;
  onResize(width: number): void; onResizeEnd(): void; onSave(user: BotUser): Promise<void>;
}) {
  const [draft, setDraft] = useState(() => copyUser(user));
  const [blockConfirmationOpen, setBlockConfirmationOpen] = useState(false);
  const setStatus = (status: UserStatus) => setDraft((current) => ({ ...current, status }));
  const className = `user-details${closing ? " user-details--closing" : ""}`;
  const name = displayName(draft);
  return <aside className={className} style={{ width }} role="dialog" aria-modal="true" aria-label={`${name} details`} onAnimationEnd={(event) => { if (event.target === event.currentTarget && closing) onClosed(); }}>
    <ResizeHandle className="user-details__resizer" axis="horizontal" label="Resize user details" value={width} min={USER_DETAILS_MIN_WIDTH} max={USER_DETAILS_MAX_WIDTH} step={24} inverted onResize={onResize} onResizeEnd={onResizeEnd} />
    <header className="user-details__header"><span>User details</span><button type="button" aria-label="Close user details" autoFocus onClick={onClose}><CloseIcon /></button></header>
    <div className="user-details__content">
      <div className="user-details__profile"><Avatar user={draft} imageUrl={avatarUrl} large /><div><h2>{name}</h2>{draft.username && <p>@{draft.username}</p>}</div><StatusBadge status={draft.status} /></div>
      <dl className="user-details__facts">
        <div><dt>Telegram ID</dt><dd><code>{draft.telegramId}</code></dd></div>
        <div><dt>Language</dt><dd>{draft.languageCode?.toUpperCase() || "Not provided"}</dd></div>
      </dl>
      <DetailsSection title="Role">
        <Select value={draft.role} options={ROLE_OPTIONS} ariaLabel="User role" onChange={(role) => setDraft((current) => ({ ...current, role: role as UserRole }))} />
      </DetailsSection>
      <DetailsSection title="Account status">
        <div className="user-details__status-actions">
          {draft.status === "blocked" ? <button type="button" className="button--secondary" onClick={() => setStatus("active")}><RestoreIcon />Restore access</button> : <button type="button" className="button--danger" onClick={() => setBlockConfirmationOpen(true)}><BlockIcon />Block</button>}
        </div>
      </DetailsSection>
      <DetailsSection title="Internal note">
        <label className="user-details__note"><span className="sr-only">Internal note</span><textarea value={draft.note} placeholder="Add context about this user…" onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))} /></label>
      </DetailsSection>
    </div>
    <footer className="user-details__footer"><button type="button" disabled={saving} onClick={() => void onSave(draft)}>{saving ? "Saving…" : "Save changes"}</button></footer>
    <ConfirmationDialog
      open={blockConfirmationOpen}
      title={`Block ${name}?`}
      description="This person will no longer be able to interact with this bot. You can restore access later."
      confirmLabel="Block user"
      onCancel={() => setBlockConfirmationOpen(false)}
      onConfirm={() => { setStatus("blocked"); setBlockConfirmationOpen(false); }}
    />
  </aside>;
}

function DetailsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="user-details__section"><header><h3>{title}</h3></header>{children}</section>;
}

function SortableHeader({ label, sortKey, sort, onSort }: { label: string; sortKey: SortKey; sort: { key: SortKey; direction: SortDirection }; onSort(key: SortKey): void }) {
  const active = sort.key === sortKey;
  return <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}><button type="button" onClick={() => onSort(sortKey)}>{label}<SortIcon active={active} direction={sort.direction} /></button></th>;
}

function FilterControl({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="users-filter"><span>{label}</span>{children}</div>;
}

function Avatar({ user, imageUrl, large = false }: { user: BotUser; imageUrl?: string; large?: boolean }) {
  const initials = `${user.firstName?.[0] ?? ""}${user.lastName?.[0] ?? ""}`.toUpperCase() || "?";
  return <span className={`${large ? "user-avatar user-avatar--large" : "user-avatar"} user-avatar--${avatarTone(user.telegramId)}`} aria-hidden="true">{initials}{imageUrl && <img src={imageUrl} alt="" onError={(event) => { event.currentTarget.hidden = true; }} />}</span>;
}

function StatusBadge({ status }: { status: UserStatus }) {
  return <span className={`status-badge status-badge--${status}`}><span aria-hidden="true" />{STATUS_LABELS[status]}</span>;
}

function LoadErrorState({ onRetry }: { onRetry(): void }) { return <div className="users-empty"><h2>Could not load users</h2><p>Check that the project is still available and try again.</p><button type="button" className="button--secondary" onClick={onRetry}>Try again</button></div>; }
function EmptyUsersState() { return <div className="users-empty"><div className="users-empty__icon"><UsersIcon /></div><h2>No users yet</h2><p>People will appear here after they interact with this bot for the first time.</p></div>; }
function NoResultsState({ onClear }: { onClear(): void }) { return <div className="users-empty"><div className="users-empty__icon"><SearchIcon /></div><h2>No users match these filters</h2><p>Try a different search or clear the current filters.</p><button type="button" className="button--secondary" onClick={onClear}>Clear filters</button></div>; }

function compareUsers(left: BotUser, right: BotUser, sort: { key: SortKey; direction: SortDirection }): number {
  const factor = sort.direction === "asc" ? 1 : -1;
  const values: Record<SortKey, [string, string]> = {
    user: [displayName(left).toLocaleLowerCase(), displayName(right).toLocaleLowerCase()],
    role: [left.role, right.role],
    status: [left.status, right.status],
  };
  return values[sort.key][0].localeCompare(values[sort.key][1]) * factor;
}

function displayName(user: BotUser): string {
  return [user.firstName, user.lastName].filter(Boolean).join(" ") || (user.username ? `@${user.username}` : `User ${user.telegramId}`);
}

function userAvatarUrl(baseUrl: string, projectId: string | undefined, user: BotUser): string | undefined {
  if (!projectId || !user.avatarVersion) return undefined;
  const base = baseUrl.replace(/\/$/, "");
  return `${base}/api/v1/projects/${encodeURIComponent(projectId)}/users/${encodeURIComponent(user.telegramId)}/avatar?v=${encodeURIComponent(user.avatarVersion)}`;
}

function copyUser(user: BotUser): BotUser { return { ...user }; }
function loadUserDetailsWidth(): number {
  if (typeof window === "undefined") return USER_DETAILS_DEFAULT_WIDTH;
  try {
    const stored = Number(window.localStorage.getItem(USER_DETAILS_WIDTH_KEY));
    return clampUserDetailsWidth(Number.isFinite(stored) && stored > 0 ? stored : USER_DETAILS_DEFAULT_WIDTH);
  } catch { return USER_DETAILS_DEFAULT_WIDTH; }
}
function saveUserDetailsWidth(width: number): void {
  try { window.localStorage.setItem(USER_DETAILS_WIDTH_KEY, String(Math.round(width))); } catch { /* Storage is optional. */ }
}
function clampUserDetailsWidth(width: number): number {
  const viewportMaximum = typeof window === "undefined" ? USER_DETAILS_MAX_WIDTH : Math.max(USER_DETAILS_MIN_WIDTH, window.innerWidth - 96);
  return Math.round(Math.min(Math.max(width, USER_DETAILS_MIN_WIDTH), USER_DETAILS_MAX_WIDTH, viewportMaximum));
}
function avatarTone(id: string): number { return (Array.from(id).reduce((sum, character) => sum + character.charCodeAt(0), 0) % 5) + 1; }

function SearchIcon() { return <Search aria-hidden="true" />; }
function CloseIcon() { return <X aria-hidden="true" />; }
function SortIcon({ active, direction }: { active: boolean; direction: SortDirection }) {
  const Icon = !active ? ChevronsUpDown : direction === "asc" ? ArrowUp : ArrowDown;
  return <Icon className={active ? "sort-icon sort-icon--active" : "sort-icon"} aria-hidden="true" />;
}
function UsersIcon() { return <UsersRound aria-hidden="true" />; }
function RestoreIcon() { return <RotateCcw aria-hidden="true" />; }
function BlockIcon() { return <LockKeyhole aria-hidden="true" />; }
