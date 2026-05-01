'use client'

import { useMemo } from 'react'
import { CircleMarker, MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

type ListingMiniMapProps = {
  latitude: number
  longitude: number
}

const MAP_BOX = 'h-[5.5rem] w-[7.5rem] max-w-full'

/** Small non-interactive OSM preview for a geocoded listing. */
export function ListingMiniMap({ latitude, longitude }: ListingMiniMapProps) {
  const center = useMemo((): [number, number] => [latitude, longitude], [latitude, longitude])

  return (
    <div
      className={`relative block ${MAP_BOX} overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700`}
    >
      <MapContainer
        key={`${latitude},${longitude}`}
        center={center}
        zoom={12}
        scrollWheelZoom={false}
        dragging={false}
        doubleClickZoom={false}
        touchZoom={false}
        boxZoom={false}
        keyboard={false}
        attributionControl={false}
        zoomControl={false}
        className={`z-0 !h-[5.5rem] !w-[7.5rem] max-w-full rounded-lg`}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <CircleMarker
          center={center}
          radius={6}
          pathOptions={{ color: '#2563eb', fillColor: '#2563eb', fillOpacity: 0.85, weight: 2 }}
        />
      </MapContainer>
    </div>
  )
}
