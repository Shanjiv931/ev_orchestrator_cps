import { useEffect, useState } from "react";
import {
  DatabaseIcon, PencilSimpleIcon, TrashIcon, PlusIcon, XIcon, CheckIcon,
  CaretLeftIcon, CaretRightIcon,
} from "@phosphor-icons/react";
import { api, ApiError } from "../../api/client";
import type { DbColumn, DbRow, DbRowsResponse, DbTable } from "../../api/types";
import { GlassCard } from "../../components/ui/GlassCard";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

const PAGE_SIZE = 25;

function isBooleanColumn(col: DbColumn): boolean {
  return col.type === "BOOLEAN";
}

function toFormValue(value: DbRow[string]): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function primaryKeyOf(table: DbTable): DbColumn | undefined {
  return table.columns.find((c) => c.primary_key);
}

export function AdminDatabasePage() {
  const [tables, setTables] = useState<DbTable[]>([]);
  const [selectedTableName, setSelectedTableName] = useState("");
  const [data, setData] = useState<DbRowsResponse | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingRowKey, setEditingRowKey] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string | boolean>>({});
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const selectedTable = tables.find((t) => t.name === selectedTableName) ?? null;
  const pk = selectedTable ? primaryKeyOf(selectedTable) : undefined;
  const editableColumns = selectedTable ? selectedTable.columns.filter((c) => !c.primary_key) : [];

  async function loadTables() {
    try {
      const list = await api.get<DbTable[]>("/admin/db/tables");
      setTables(list);
      if (list.length > 0 && !selectedTableName) setSelectedTableName(list[0].name);
    } catch {
      setError("You need admin access to view this page.");
    }
  }

  async function loadRows(tableName: string, atOffset: number) {
    setLoading(true);
    try {
      const result = await api.get<DbRowsResponse>(`/admin/db/tables/${tableName}/rows?limit=${PAGE_SIZE}&offset=${atOffset}`);
      setData(result);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTables(); }, []);
  useEffect(() => {
    if (!selectedTableName) return;
    setOffset(0);
    setEditingRowKey(null);
    setAdding(false);
    loadRows(selectedTableName, 0);
  }, [selectedTableName]);

  function goToPage(newOffset: number) {
    setOffset(newOffset);
    loadRows(selectedTableName, newOffset);
  }

  function startEdit(row: DbRow) {
    if (!pk) return;
    setAdding(false);
    setEditingRowKey(String(row[pk.name]));
    const values: Record<string, string | boolean> = {};
    for (const col of editableColumns) {
      values[col.name] = isBooleanColumn(col) ? Boolean(row[col.name]) : toFormValue(row[col.name]);
    }
    setEditValues(values);
  }

  function startAdd() {
    setEditingRowKey(null);
    setAdding(true);
    const values: Record<string, string | boolean> = {};
    for (const col of editableColumns) {
      values[col.name] = isBooleanColumn(col) ? false : "";
    }
    setEditValues(values);
  }

  function cancelEdit() {
    setEditingRowKey(null);
    setAdding(false);
    setError(null);
  }

  function buildPayload(forCreate: boolean): Record<string, string | boolean | null> {
    const payload: Record<string, string | boolean | null> = {};
    for (const col of editableColumns) {
      const raw = editValues[col.name];
      if (isBooleanColumn(col)) {
        payload[col.name] = raw as boolean;
        continue;
      }
      const text = (raw as string).trim();
      if (text === "") {
        // Leave defaulted/nullable columns alone on create (skip the key
        // entirely so the DB's own default applies); an edit that clears a
        // nullable field is a deliberate "set to null".
        if (forCreate) continue;
        payload[col.name] = col.nullable ? null : "";
      } else {
        payload[col.name] = text;
      }
    }
    return payload;
  }

  async function saveEdit(row: DbRow) {
    if (!pk || !selectedTableName) return;
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/admin/db/tables/${selectedTableName}/rows/${row[pk.name]}`, buildPayload(false));
      cancelEdit();
      loadRows(selectedTableName, offset);
      loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save row.");
    } finally {
      setBusy(false);
    }
  }

  async function saveNew() {
    if (!selectedTableName) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/admin/db/tables/${selectedTableName}/rows`, buildPayload(true));
      cancelEdit();
      loadRows(selectedTableName, offset);
      loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create row.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteRow(row: DbRow) {
    if (!pk || !selectedTableName) return;
    if (!confirm(`Delete this ${selectedTableName} row? This can't be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.delete(`/admin/db/tables/${selectedTableName}/rows/${row[pk.name]}`);
      loadRows(selectedTableName, offset);
      loadTables();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete row - it may still be referenced elsewhere.");
    } finally {
      setBusy(false);
    }
  }

  function renderCellInput(col: DbColumn) {
    if (isBooleanColumn(col)) {
      return (
        <input type="checkbox" checked={Boolean(editValues[col.name])}
               onChange={(e) => setEditValues((prev) => ({ ...prev, [col.name]: e.target.checked }))} />
      );
    }
    return (
      <Input value={(editValues[col.name] as string) ?? ""} placeholder={col.nullable ? "null" : ""}
             onChange={(e) => setEditValues((prev) => ({ ...prev, [col.name]: e.target.value }))}
             className="text-xs !py-1 !px-2 min-w-28" />
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <DatabaseIcon size={24} weight="duotone" className="text-emerald-400" />
        <h1 className="font-display text-2xl font-bold">Database</h1>
      </div>

      {error && !selectedTable && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {tables.length > 0 && (
        <div className="flex gap-1.5 mb-4 overflow-x-auto pb-1">
          {tables.map((t) => (
            <button key={t.name} onClick={() => setSelectedTableName(t.name)}
                    className={`shrink-0 text-xs px-3 py-1.5 rounded-lg cursor-pointer transition-colors ${
                      t.name === selectedTableName ? "bg-emerald-500/20 text-emerald-300" : "text-slate-400 hover:bg-white/5"
                    }`}>
              {t.name} <span className="text-slate-500">({t.row_count})</span>
            </button>
          ))}
        </div>
      )}

      {selectedTable && data && (
        <>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-slate-500">
              {data.total === 0 ? "No rows" : `${offset + 1}-${Math.min(offset + data.rows.length, data.total)} of ${data.total}`}
            </p>
            <div className="flex items-center gap-2">
              <Button variant="ghost" className="!py-1 !px-2" disabled={offset === 0} onClick={() => goToPage(Math.max(0, offset - PAGE_SIZE))}>
                <CaretLeftIcon size={14} />
              </Button>
              <Button variant="ghost" className="!py-1 !px-2" disabled={offset + PAGE_SIZE >= data.total} onClick={() => goToPage(offset + PAGE_SIZE)}>
                <CaretRightIcon size={14} />
              </Button>
              <Button onClick={startAdd} disabled={adding} className="!py-1 !px-2.5 text-xs">
                <PlusIcon size={13} weight="bold" /> Add row
              </Button>
            </div>
          </div>

          {error && <p className="text-red-400 text-xs mb-3">{error}</p>}

          <div className="overflow-x-auto rounded-2xl glass-panel">
            <table className="text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-white/10">
                  {selectedTable.columns.map((col) => (
                    <th key={col.name} className="px-3 py-2.5 whitespace-nowrap">
                      {col.name}{col.primary_key && " 🔑"}
                    </th>
                  ))}
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {adding && (
                  <tr className="bg-emerald-500/5">
                    {selectedTable.columns.map((col) => (
                      <td key={col.name} className="px-3 py-2 whitespace-nowrap">
                        {col.primary_key ? <span className="text-slate-600 text-xs">auto</span> : renderCellInput(col)}
                      </td>
                    ))}
                    <td className="px-3 py-2 whitespace-nowrap">
                      <div className="flex gap-1">
                        <button onClick={saveNew} disabled={busy} className="text-emerald-400 hover:text-emerald-300 cursor-pointer"><CheckIcon size={16} /></button>
                        <button onClick={cancelEdit} disabled={busy} className="text-slate-400 hover:text-slate-200 cursor-pointer"><XIcon size={16} /></button>
                      </div>
                    </td>
                  </tr>
                )}
                {data.rows.map((row) => {
                  const rowKey = pk ? String(row[pk.name]) : JSON.stringify(row);
                  const isEditing = editingRowKey === rowKey;
                  return (
                    <tr key={rowKey} className="hover:bg-white/[0.02]">
                      {selectedTable.columns.map((col) => (
                        <td key={col.name} className="px-3 py-2 whitespace-nowrap font-mono text-xs">
                          {isEditing && !col.primary_key ? renderCellInput(col) : (
                            col.primary_key
                              ? <span className="text-slate-500">{toFormValue(row[col.name]).slice(0, 8)}</span>
                              : toFormValue(row[col.name]) || <span className="text-slate-600">null</span>
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-2 whitespace-nowrap">
                        <div className="flex gap-1">
                          {isEditing ? (
                            <>
                              <button onClick={() => saveEdit(row)} disabled={busy} className="text-emerald-400 hover:text-emerald-300 cursor-pointer"><CheckIcon size={16} /></button>
                              <button onClick={cancelEdit} disabled={busy} className="text-slate-400 hover:text-slate-200 cursor-pointer"><XIcon size={16} /></button>
                            </>
                          ) : (
                            <>
                              <button onClick={() => startEdit(row)} disabled={!pk} className="text-cyan-400 hover:text-cyan-300 cursor-pointer disabled:opacity-30"><PencilSimpleIcon size={15} /></button>
                              <button onClick={() => deleteRow(row)} disabled={!pk} className="text-red-400 hover:text-red-300 cursor-pointer disabled:opacity-30"><TrashIcon size={15} /></button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {data.rows.length === 0 && !adding && (
                  <tr><td colSpan={selectedTable.columns.length + 1} className="px-3 py-6 text-center text-slate-500">Empty table.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {!pk && (
            <p className="text-[11px] text-amber-400/80 mt-2">
              This table has no single-column primary key, so rows can't be edited or deleted here - view only.
            </p>
          )}
        </>
      )}

      {loading && <p className="text-sm text-slate-500 text-center py-6">Loading...</p>}
    </div>
  );
}
