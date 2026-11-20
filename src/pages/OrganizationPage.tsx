import { useState, useEffect, useRef, type FormEvent } from "react";
import {
  Building2,
  Plus,
  RefreshCw,
  MapPin,
  Layers,
  Pencil,
  X,
  Save,
} from "lucide-react";
import { api, post } from "../api";
import { Button, Spinner, Empty } from "../components/ui";

type Organization = {
  id: string;
  name: string;
  description: string;
  configured: boolean;
  version: number;
  can_edit: boolean;
};
type Site = { id: string; name: string; display_name: string; assets: number };
type Node = {
  id: string;
  site_id: string;
  area_id?: string;
  code: string;
  name: string;
  version: number;
};
type Equipment = {
  id: string;
  tag: string;
  name: string;
  location: string;
  system_id: string | null;
  placement_version: number;
};
type Hierarchy = {
  site: { id: string; name: string };
  areas: Node[];
  systems: Node[];
  equipment: Equipment[];
  can_configure: boolean;
  can_assign: boolean;
};
type Edit = { kind: "areas" | "systems"; node: Node };

function EquipmentPlacementRow({
  equipment,
  hierarchy,
  busy,
  onSave,
  openAsset,
}: {
  equipment: Equipment;
  hierarchy: Hierarchy;
  busy: boolean;
  onSave: (id: string, system: string, version: number) => void;
  openAsset: (id: string) => void;
}) {
  const [target, setTarget] = useState(equipment.system_id || "");
  useEffect(
    () => setTarget(equipment.system_id || ""),
    [equipment.system_id, equipment.placement_version],
  );
  return (
    <tr>
      <td>
        <button className="text-link" onClick={() => openAsset(equipment.id)}>
          {equipment.tag}
        </button>
        <small>{equipment.name}</small>
      </td>
      <td>
        <select
          aria-label={`System for ${equipment.tag}`}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          disabled={busy || !hierarchy.can_assign}
        >
          <option value="">Unassigned</option>
          {hierarchy.systems.map((system) => (
            <option key={system.id} value={system.id}>
              {hierarchy.areas.find((a) => a.id === system.area_id)?.code} /{" "}
              {system.code} · {system.name}
            </option>
          ))}
        </select>
      </td>
      <td>
        <Button
          icon={Save}
          disabled={
            busy ||
            !hierarchy.can_assign ||
            target === (equipment.system_id || "")
          }
          onClick={() =>
            onSave(equipment.id, target, equipment.placement_version)
          }
        >
          Save placement
        </Button>
      </td>
    </tr>
  );
}

export function OrganizationPage({
  openAsset,
  selectedSite,
  selectSite,
}: {
  openAsset: (id: string) => void;
  selectedSite: string;
  selectSite: (name: string) => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("");
  const [hierarchy, setHierarchy] = useState<Hierarchy | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [form, setForm] = useState<"area" | "system" | "site" | null>(null);
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [areaId, setAreaId] = useState("");
  const [edit, setEdit] = useState<Edit | null>(null);
  useEffect(() => {
    if (form || edit) formRef.current?.scrollIntoView({ block: "start" });
  }, [form, edit]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      api<Organization>("/foundation/organization"),
      api<{ items: Site[] }>("/sites"),
    ])
      .then(([org, directory]) => {
        if (!active) return;
        setOrganization(org);
        setName(org.name);
        setDescription(org.description);
        setSites(directory.items);
        setSiteId(
          (previous) =>
            directory.items.find((s) => s.name === selectedSite)?.id ||
            (directory.items.some((s) => s.id === previous)
              ? previous
              : directory.items[0]?.id || ""),
        );
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [reload, selectedSite]);
  useEffect(() => {
    setHierarchy(null);
    setForm(null);
    setEdit(null);
    if (!siteId) return;
    let active = true;
    api<Hierarchy>(
      "/foundation/hierarchy?site_id=" + encodeURIComponent(siteId),
    )
      .then((data) => {
        if (active) setHierarchy(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [siteId, reload]);
  async function mutate(action: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(message);
      setForm(null);
      setEdit(null);
      setReload((x) => x + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function begin(next: "area" | "system" | "site") {
    setForm(next);
    setEdit(null);
    setCode("");
    setLabel("");
    setAreaId(hierarchy?.areas[0]?.id || "");
  }
  function startEdit(kind: "areas" | "systems", node: Node) {
    setEdit({ kind, node });
    setForm(null);
    setCode(node.code);
    setLabel(node.name);
  }
  function saveStructure(event: FormEvent) {
    event.preventDefault();
    if (edit) {
      mutate(
        () =>
          api("/foundation/" + edit.kind + "/" + edit.node.id, {
            method: "PATCH",
            body: JSON.stringify({
              code,
              name: label,
              expected_version: edit.node.version,
            }),
          }),
        "Hierarchy labels saved. Equipment identities are unchanged.",
      );
    } else if (form === "site") {
      mutate(
        () =>
          post("/foundation/sites", {
            name: label,
            expected_organization_version: organization!.version,
          }),
        "Site created and assigned to your administrator account. Refresh the browser to update the portal-wide site selector. Other user memberships are unchanged.",
      );
    } else {
      mutate(
        () =>
          post("/foundation/" + (form === "area" ? "areas" : "systems"), {
            code,
            name: label,
            ...(form === "area" ? { site_id: siteId } : { area_id: areaId }),
          }),
        form === "area" ? "Site area created." : "Equipment system created.",
      );
    }
  }
  if (loading && !organization) return <Spinner />;
  return (
    <div className="organization-workspace">
      {error && (
        <div className="form-error" role="alert">
          {error}{" "}
          <Button onClick={() => setReload((x) => x + 1)} disabled={busy}>
            Refresh records
          </Button>
        </div>
      )}
      {notice && (
        <div className="form-success" role="status">
          {notice}
        </div>
      )}
      {!organization && !loading && (
        <Empty
          title="Organization profile unavailable"
          description="Check the application connection and database migration, then refresh records."
        />
      )}
      {organization && (
        <>
          <section className="panel organization-profile">
            <div className="organization-section-head">
              <div>
                <span className="production-eyebrow">
                  SINGLE COMPANY / MULTIPLE SITES
                </span>
                <h2>
                  <Building2 size={23} /> Organization profile
                </h2>
                <p>
                  {organization.configured
                    ? "Your saved company profile."
                    : "Set your company name to begin. Existing sites and equipment have been preserved."}
                </p>
              </div>
              <span className="organization-state">
                {organization.configured ? "Configured" : "Setup required"}
              </span>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                mutate(
                  () =>
                    api("/foundation/organization", {
                      method: "PATCH",
                      body: JSON.stringify({
                        name,
                        description,
                        expected_version: organization.version,
                      }),
                    }),
                  "Organization profile saved.",
                );
              }}
            >
              <div className="organization-profile-fields">
                <label>
                  Company name
                  <input
                    required
                    maxLength={160}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={busy || !organization.can_edit}
                  />
                </label>
                <label>
                  Description
                  <textarea
                    maxLength={500}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    disabled={busy || !organization.can_edit}
                    rows={2}
                  />
                </label>
              </div>
              <div className="organization-profile-footer">
                <p>
                  Company-wide changes require an administrator assigned to
                  every site. Display times remain in GST.
                </p>
                {organization.can_edit && (
                  <Button
                    className="primary"
                    icon={Save}
                    disabled={
                      busy ||
                      !name.trim() ||
                      (name === organization.name &&
                        description === organization.description &&
                        organization.configured)
                    }
                  >
                    Save company profile
                  </Button>
                )}
              </div>
            </form>
          </section>
          <section className="panel organization-hierarchy">
            <div className="organization-section-head">
              <div>
                <h2>
                  <MapPin size={23} /> Site & equipment hierarchy
                </h2>
                <p>Organization → site → area → system → equipment</p>
              </div>
              <Button
                icon={RefreshCw}
                disabled={busy || loading}
                onClick={() => setReload((x) => x + 1)}
              >
                Refresh
              </Button>
            </div>
            <div className="organization-toolbar">
              <label>
                Site
                <select
                  aria-label="Hierarchy site"
                  value={siteId}
                  onChange={(e) => {
                    setError("");
                    setSiteId(e.target.value);
                    const selected = sites.find(
                      (site) => site.id === e.target.value,
                    );
                    if (selected) selectSite(selected.name);
                  }}
                  disabled={busy}
                >
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <div>
                {organization.can_edit && (
                  <Button
                    icon={Plus}
                    disabled={busy}
                    onClick={() => begin("site")}
                  >
                    Add site
                  </Button>
                )}
                {hierarchy?.can_configure && (
                  <>
                    <Button
                      icon={Plus}
                      disabled={busy}
                      onClick={() => begin("area")}
                    >
                      Add area
                    </Button>
                    <Button
                      icon={Plus}
                      disabled={busy || !hierarchy.areas.length}
                      onClick={() => begin("system")}
                    >
                      Add system
                    </Button>
                  </>
                )}
              </div>
            </div>
            {(form || edit) && (
              <form
                ref={formRef}
                className="organization-node-form"
                onSubmit={saveStructure}
              >
                <div className="organization-form-title">
                  <h3>
                    {edit
                      ? "Edit " + (edit.kind === "areas" ? "area" : "system")
                      : form === "site"
                        ? "Create site"
                        : form === "area"
                          ? "Create area"
                          : "Create system"}
                  </h3>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Close hierarchy form"
                    onClick={() => {
                      setForm(null);
                      setEdit(null);
                    }}
                    disabled={busy}
                  >
                    <X size={20} />
                  </button>
                </div>
                <div className="organization-node-fields">
                  {form === "system" && (
                    <label>
                      Parent area
                      <select
                        aria-label="Parent area"
                        required
                        value={areaId}
                        onChange={(e) => setAreaId(e.target.value)}
                        disabled={busy}
                      >
                        {hierarchy?.areas.map((area) => (
                          <option key={area.id} value={area.id}>
                            {area.code} · {area.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {form !== "site" && (
                    <label>
                      Code
                      <input
                        required
                        maxLength={30}
                        pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,29}"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        disabled={busy}
                        placeholder="e.g. UTILITIES"
                      />
                    </label>
                  )}
                  <label>
                    {form === "site" ? "Site name" : "Name"}
                    <input
                      required
                      maxLength={form === "site" ? 100 : 120}
                      value={label}
                      onChange={(e) => setLabel(e.target.value)}
                      disabled={busy}
                    />
                  </label>
                </div>
                <p>
                  {form === "site"
                    ? "Creates an empty site. Only your administrator account receives membership; other users retain their current access."
                    : "Codes are unique within their parent. Areas and systems cannot be moved across sites."}
                </p>
                <Button
                  className="primary"
                  disabled={
                    busy ||
                    !label.trim() ||
                    (form !== "site" && !code.trim()) ||
                    (form === "system" && !areaId)
                  }
                >
                  Save {edit ? "changes" : form}
                </Button>
              </form>
            )}
            {!hierarchy && siteId ? (
              <Spinner />
            ) : (
              hierarchy && (
                <>
                  <div className="organization-hierarchy-summary">
                    <span>
                      <strong>{hierarchy.areas.length}</strong> areas
                    </span>
                    <span>
                      <strong>{hierarchy.systems.length}</strong> systems
                    </span>
                    <span>
                      <strong>
                        {hierarchy.equipment.filter((a) => a.system_id).length}
                      </strong>{" "}
                      assigned equipment
                    </span>
                    <span>
                      <strong>
                        {hierarchy.equipment.filter((a) => !a.system_id).length}
                      </strong>{" "}
                      unassigned
                    </span>
                  </div>
                  <div className="organization-tree">
                    {hierarchy.areas.map((area) => (
                      <article key={area.id}>
                        <div className="organization-tree-heading">
                          <div>
                            <Layers size={20} />
                            <strong>{area.code}</strong>
                            <span>{area.name}</span>
                          </div>
                          {hierarchy.can_configure && (
                            <Button
                              icon={Pencil}
                              disabled={busy}
                              onClick={() => startEdit("areas", area)}
                            >
                              Edit area
                            </Button>
                          )}
                        </div>
                        <div className="organization-system-list">
                          {hierarchy.systems
                            .filter((system) => system.area_id === area.id)
                            .map((system) => (
                              <div key={system.id}>
                                <div>
                                  <strong>
                                    {system.code} · {system.name}
                                  </strong>
                                  <span>
                                    {
                                      hierarchy.equipment.filter(
                                        (a) => a.system_id === system.id,
                                      ).length
                                    }{" "}
                                    equipment assigned
                                  </span>
                                </div>
                                {hierarchy.can_configure && (
                                  <Button
                                    icon={Pencil}
                                    disabled={busy}
                                    onClick={() => startEdit("systems", system)}
                                  >
                                    Edit system
                                  </Button>
                                )}
                              </div>
                            ))}
                          {!hierarchy.systems.some(
                            (system) => system.area_id === area.id,
                          ) && (
                            <p>
                              No systems in this area. Add a system to organize
                              equipment.
                            </p>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                  {!hierarchy.areas.length && (
                    <Empty
                      title="Create your first area"
                      description="Existing equipment stays unassigned until you create areas and systems. Original location labels are preserved."
                    />
                  )}
                  <div className="organization-equipment-heading">
                    <h3>Equipment placement</h3>
                    <p>
                      {hierarchy.can_assign
                        ? "Select a system and save each assignment. Existing equipment IDs, location labels and readings remain unchanged."
                        : "View equipment placement within your permitted site. An administrator or engineer manages assignments."}
                    </p>
                  </div>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Equipment</th>
                          <th>Area / system</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {hierarchy.equipment.map((equipment) => (
                          <EquipmentPlacementRow
                            key={equipment.id}
                            equipment={equipment}
                            hierarchy={hierarchy}
                            busy={busy}
                            openAsset={openAsset}
                            onSave={(id, system, version) =>
                              mutate(
                                () =>
                                  api(
                                    "/foundation/equipment/" +
                                      id +
                                      "/placement",
                                    {
                                      method: "PUT",
                                      body: JSON.stringify({
                                        system_id: system || null,
                                        expected_version: version,
                                      }),
                                    },
                                  ),
                                "Equipment placement saved.",
                              )
                            }
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!hierarchy.equipment.length && (
                    <Empty
                      title="No equipment at this site"
                      description="Register equipment in Asset registry before assigning it to a system."
                    />
                  )}
                </>
              )
            )}
          </section>
        </>
      )}
    </div>
  );
}
