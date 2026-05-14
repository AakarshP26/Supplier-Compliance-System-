"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface MapSupplier {
  id: string;
  name: string;
  lat: number;
  lng: number;
  address: string | null;
  category: string;
  score: number | null;
  grade: string | null;
  is_illustrative: boolean;
  compliance_fails: number;
}

interface Props {
  suppliers: MapSupplier[];
  gradeColors: Record<string, string>;
  onSelect: (s: MapSupplier) => void;
  selected: MapSupplier | null;
}

function makeIcon(color: string, size = 10): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:${size}px;height:${size}px;
      border-radius:50%;
      background:${color};
      border:1.5px solid rgba(255,255,255,0.25);
      box-shadow:0 0 6px ${color}80;
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  });
}

export default function MapView({ suppliers, gradeColors, onSelect, selected }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [12.9716, 77.5946], // Bengaluru centre
      zoom: 11,
      zoomControl: false,
    });

    // Dark tile layer — CartoDB Dark Matter (free, no key)
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> © <a href="https://carto.com/">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 19,
      }
    ).addTo(map);

    L.control.zoom({ position: "topright" }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Re-draw markers when suppliers or selection changes
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    suppliers.forEach((s) => {
      const color = s.grade ? (gradeColors[s.grade] ?? "#6366f1") : "rgba(255,255,255,0.2)";
      const isSelected = selected?.id === s.id;
      const icon = makeIcon(color, isSelected ? 14 : 9);

      const marker = L.marker([s.lat, s.lng], { icon })
        .addTo(layer)
        .on("click", () => onSelect(s));

      // Tooltip on hover
      marker.bindTooltip(
        `<div style="
          background:#111;
          border:1px solid rgba(255,255,255,0.1);
          border-radius:6px;
          padding:8px 10px;
          font-family:monospace;
          font-size:11px;
          color:rgba(255,255,255,0.8);
          white-space:nowrap;
          pointer-events:none;
        ">
          <strong style="font-size:12px;color:#fff;">${s.name}</strong><br/>
          ${s.grade ? `<span style="color:${color}">Grade ${s.grade}</span> · Score ${s.score?.toFixed(1) ?? "—"}` : "<span style='color:rgba(255,255,255,0.4)'>Unscored</span>"}<br/>
          <span style="color:rgba(255,255,255,0.4)">${s.category.replace(/_/g, " ")}</span>
          ${s.compliance_fails > 0 ? `<br/><span style="color:#ef4444">${s.compliance_fails} compliance fail(s)</span>` : ""}
        </div>`,
        { className: "leaflet-dark-tooltip", direction: "top", offset: [0, -6] }
      );
    });

    // Pan to selected
    if (selected) {
      map.panTo([selected.lat, selected.lng], { animate: true, duration: 0.4 });
    }
  }, [suppliers, selected, gradeColors, onSelect]);

  return (
    <>
      <style>{`
        .leaflet-dark-tooltip {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          padding: 0 !important;
        }
        .leaflet-dark-tooltip::before { display: none !important; }
        .leaflet-container { background: #0a0a0a; }
        .leaflet-control-attribution {
          background: rgba(0,0,0,0.6) !important;
          color: rgba(255,255,255,0.2) !important;
          font-size: 9px !important;
        }
        .leaflet-control-attribution a { color: rgba(255,255,255,0.3) !important; }
        .leaflet-control-zoom a {
          background: #111 !important;
          color: rgba(255,255,255,0.6) !important;
          border-color: rgba(255,255,255,0.1) !important;
        }
        .leaflet-control-zoom a:hover {
          background: #1a1a1a !important;
          color: rgba(255,255,255,0.9) !important;
        }
      `}</style>
      <div ref={containerRef} className="w-full h-full" />
    </>
  );
}
