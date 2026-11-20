import { useState, useEffect } from "react";
import { Sparkles, TriangleAlert } from "lucide-react";
import {
  api,
  age,
  human,
  type Asset,
  type Reading,
  type Episode,
} from "../../api";

import { Badge, Button, Spinner, Modal, Chart, EquipmentArt } from "../ui";

export function AssetDrawer({
  id,
  onClose,
  refreshKey,
  onInvestigate,
  canInvestigate,
  busy,
}: {
  id: string;
  onClose: () => void;
  refreshKey: number;
  onInvestigate: (id: string) => void;
  canInvestigate: boolean;
  busy: boolean;
}) {
  const [detail, setDetail] = useState<{
      asset: Asset;
      readings: Reading[];
      episodes: Episode[];
    } | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let done = false;
    api<typeof detail>("/assets/" + id)
      .then((r) => {
        if (!done) setDetail(r);
      })
      .catch((e) => setError(e.message));
    return () => {
      done = true;
    };
  }, [id, refreshKey]);
  const a = detail?.asset;
  return (
    <Modal
      wide
      title={a ? `${a.tag} · ${a.name}` : "Equipment workspace"}
      description={a?.location}
      onClose={onClose}
    >
      {error ? (
        <p className="form-error">{error}</p>
      ) : !detail || !a ? (
        <Spinner />
      ) : (
        <>
          <div className="asset-detail-hero">
            <div>
              <Badge value={a.status} />
              <h3>{a.kind} condition</h3>
              <strong>
                {a.health ?? "—"}
                <small>/100</small>
              </strong>
              <p>Transparent condition index</p>
              <span className="small-text muted">{a.site}</span>
            </div>
            <EquipmentArt kind={a.kind} size="large" />
            <div className="detail-identity">
              <span>CRITICALITY</span>
              <strong>{a.criticality}</strong>
              <span>LAST READING</span>
              <strong>
                {a.reading ? age(a.reading.timestamp) : "No readings"}
              </strong>
              <span>ANOMALY DETECTOR</span>
              <strong>
                {a.anomaly
                  ? "Outside synthetic baseline"
                  : "Within synthetic baseline"}
              </strong>
            </div>
          </div>
          <div className="detail-metrics">
            {(["vibration", "temperature", "pressure", "flow"] as const).map(
              (f) => (
                <div key={f}>
                  <span>{human(f)}</span>
                  <strong>
                    {a.reading?.[f].toFixed(2) ?? "—"}
                    <small>
                      {
                        {
                          vibration: "mm/s",
                          temperature: "°C",
                          pressure: "bar",
                          flow: "m³/h",
                        }[f]
                      }
                    </small>
                  </strong>
                </div>
              ),
            )}
          </div>
          <div className="modal-section">
            <h3>Vibration history</h3>
            <Chart data={detail.readings} threshold={a.threshold} />
            <div className="local-note">
              <TriangleAlert size={16} />
              The limit is a configurable demonstration value, not an OEM or
              certified safety threshold.
            </div>
          </div>
          <div className="modal-section">
            <h3>Condition episodes</h3>
            {detail.episodes.length ? (
              detail.episodes.map((e) => (
                <div className="inline-episode" key={e.id}>
                  <TriangleAlert size={15} />
                  <span>{e.title}</span>
                  <Badge value={e.state} />
                </div>
              ))
            ) : (
              <p className="muted">
                No condition episodes recorded for this equipment.
              </p>
            )}
          </div>
          <div className="modal-actions">
            <Button onClick={onClose}>Close</Button>
            <Button
              className="primary"
              icon={Sparkles}
              disabled={!canInvestigate || busy || !a.reading}
              onClick={() => onInvestigate(id)}
            >
              {busy ? "Preparing…" : "Investigate equipment"}
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
