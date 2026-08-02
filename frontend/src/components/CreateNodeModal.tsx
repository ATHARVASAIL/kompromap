import { useState } from "react";
import { createNode } from "../api/client";
import ErrorBanner from "./ErrorBanner";
import Spinner from "./Spinner";
import { useToast } from "./toastContext";
import { NODE_TYPE_LABELS, type NodeType } from "../types/graph";

interface CreateNodeModalProps {
  onClose: () => void;
  onCreated: () => void;
}

const NODE_TYPES = Object.keys(NODE_TYPE_LABELS) as NodeType[];

const ASSET_TYPES = ["domain", "subdomain", "ip", "cloud_resource"];
const CRED_TYPES = ["password", "api_key", "session_token", "ssh_key"];
const PRIVILEGE_LEVELS = ["admin", "standard", "service"];
const DATA_CLASSIFICATIONS = ["PII", "PCI", "none"];
const FINDING_STATUSES = ["open", "fixed", "accepted-risk"];

export default function CreateNodeModal({ onClose, onCreated }: CreateNodeModalProps) {
  const { toast } = useToast();
  const [nodeType, setNodeType] = useState<NodeType>("asset");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function set(key: string, value: string) {
    setFields((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = buildPayload(nodeType, fields);
      await createNode(payload);
      toast(`${NODE_TYPE_LABELS[nodeType]} created`, "success");
      onCreated();
    } catch (err) {
      setError(String(err));
      toast("Couldn't create node", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 font-mono text-sm">
      <form
        onSubmit={handleSubmit}
        className="w-96 animate-fade-in-scale rounded border border-border bg-surface-1 p-5 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-text-primary">create node</h2>
          <button type="button" onClick={onClose} className="text-text-tertiary hover:text-text-primary">
            ✕
          </button>
        </div>

        <label className="mb-1 block text-xs text-text-tertiary">node type</label>
        <select
          value={nodeType}
          onChange={(e) => {
            setNodeType(e.target.value as NodeType);
            setFields({});
          }}
          className="mb-4 w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
        >
          {NODE_TYPES.map((t) => (
            <option key={t} value={t}>
              {NODE_TYPE_LABELS[t]}
            </option>
          ))}
        </select>

        <div className="space-y-3">{renderFields(nodeType, fields, set)}</div>

        {error && <ErrorBanner message={error} className="mt-3" />}

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded border border-border py-1.5 text-text-tertiary hover:border-border-strong"
          >
            cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex flex-1 items-center justify-center gap-2 rounded border border-accent bg-accent/10 py-1.5 text-accent hover:bg-accent/20 disabled:opacity-50"
          >
            {saving && <Spinner />}
            {saving ? "creating…" : "create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-text-tertiary">{label}</label>
      <input
        type="text"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
      />
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-text-tertiary">{label}</label>
      <select
        value={value ?? options[0]}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-border bg-surface-0 px-2 py-1.5 text-text-primary focus:border-accent focus:outline-none"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function renderFields(
  nodeType: NodeType,
  fields: Record<string, string>,
  set: (key: string, value: string) => void,
) {
  switch (nodeType) {
    case "asset":
      return (
        <>
          <TextField label="name" value={fields.name} onChange={(v) => set("name", v)} required />
          <SelectField
            label="asset type"
            value={fields.asset_type}
            options={ASSET_TYPES}
            onChange={(v) => set("asset_type", v)}
          />
        </>
      );
    case "service":
      return (
        <>
          <TextField label="port" value={fields.port} onChange={(v) => set("port", v)} required />
          <TextField
            label="protocol (tcp/udp)"
            value={fields.protocol || "tcp"}
            onChange={(v) => set("protocol", v)}
            required
          />
          <TextField label="banner" value={fields.banner} onChange={(v) => set("banner", v)} />
        </>
      );
    case "web_application":
      return (
        <>
          <TextField label="name" value={fields.name} onChange={(v) => set("name", v)} required />
          <TextField label="base url" value={fields.base_url} onChange={(v) => set("base_url", v)} required />
          <TextField label="auth type" value={fields.auth_type} onChange={(v) => set("auth_type", v)} />
        </>
      );
    case "endpoint":
      return (
        <>
          <TextField label="path" value={fields.path} onChange={(v) => set("path", v)} required />
          <TextField label="method" value={fields.method || "GET"} onChange={(v) => set("method", v)} />
        </>
      );
    case "credential":
      return (
        <>
          <SelectField
            label="credential type"
            value={fields.cred_type}
            options={CRED_TYPES}
            onChange={(v) => set("cred_type", v)}
          />
          <TextField label="scope" value={fields.scope} onChange={(v) => set("scope", v)} />
        </>
      );
    case "account":
      return (
        <>
          <TextField label="username" value={fields.username} onChange={(v) => set("username", v)} required />
          <SelectField
            label="privilege level"
            value={fields.privilege_level}
            options={PRIVILEGE_LEVELS}
            onChange={(v) => set("privilege_level", v)}
          />
        </>
      );
    case "data_store":
      return (
        <>
          <TextField label="name" value={fields.name} onChange={(v) => set("name", v)} required />
          <SelectField
            label="data classification"
            value={fields.data_classification}
            options={DATA_CLASSIFICATIONS}
            onChange={(v) => set("data_classification", v)}
          />
          <TextField
            label="record count estimate"
            value={fields.record_count_estimate}
            onChange={(v) => set("record_count_estimate", v)}
          />
        </>
      );
    case "finding":
      return (
        <>
          <TextField label="title" value={fields.title} onChange={(v) => set("title", v)} required />
          <TextField label="cwe" value={fields.cwe} onChange={(v) => set("cwe", v)} />
          <TextField label="cvss score" value={fields.cvss_score} onChange={(v) => set("cvss_score", v)} />
          <SelectField
            label="status"
            value={fields.status}
            options={FINDING_STATUSES}
            onChange={(v) => set("status", v)}
          />
        </>
      );
  }
}

function buildPayload(nodeType: NodeType, fields: Record<string, string>): Record<string, unknown> {
  const base = { node_type: nodeType };
  switch (nodeType) {
    case "asset":
      return { ...base, name: fields.name, asset_type: fields.asset_type || "domain" };
    case "service":
      return {
        ...base,
        port: Number(fields.port),
        protocol: fields.protocol || "tcp",
        banner: fields.banner || null,
      };
    case "web_application":
      return {
        ...base,
        name: fields.name,
        base_url: fields.base_url,
        auth_type: fields.auth_type || null,
      };
    case "endpoint":
      return { ...base, path: fields.path, method: fields.method || "GET" };
    case "credential":
      return {
        ...base,
        cred_type: fields.cred_type || "password",
        scope: fields.scope || null,
      };
    case "account":
      return {
        ...base,
        username: fields.username,
        privilege_level: fields.privilege_level || "standard",
      };
    case "data_store":
      return {
        ...base,
        name: fields.name,
        data_classification: fields.data_classification || "none",
        record_count_estimate: fields.record_count_estimate ? Number(fields.record_count_estimate) : null,
      };
    case "finding":
      return {
        ...base,
        title: fields.title,
        cwe: fields.cwe || null,
        cvss_score: fields.cvss_score ? Number(fields.cvss_score) : null,
        status: fields.status || "open",
      };
  }
}
