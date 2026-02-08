import { io, Socket } from "socket.io-client";
import { useTrackingStore } from "@/stores/tracking-store";
import type { TrackingUpdate } from "@/types";

// ---------------------------------------------------------------------------
// Socket.IO client configuration
// ---------------------------------------------------------------------------

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:5001";

let socket: Socket | null = null;

function getSocket(): Socket {
  if (!socket) {
    socket = io(WS_URL, {
      autoConnect: false,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      timeout: 20000,
      transports: ["websocket", "polling"],
    });

    // ----- Connection lifecycle events -----

    socket.on("connect", () => {
      useTrackingStore.getState().setConnected(true);
    });

    socket.on("disconnect", () => {
      useTrackingStore.getState().setConnected(false);
    });

    socket.on("connect_error", (error) => {
      console.error("[socket] connection error:", error.message);
      useTrackingStore.getState().setConnected(false);
    });

    // ----- Tracking events -----

    socket.on("tracking:update", (update: TrackingUpdate) => {
      useTrackingStore.getState().addUpdate(update);
    });

    socket.on("tracking:status", (data: { status: TrackingUpdate["status"] }) => {
      useTrackingStore.getState().setStatus(data.status);
    });

    socket.on(
      "tracking:location",
      (location: { lat: number; lng: number }) => {
        useTrackingStore.getState().setContractorLocation(location);
      }
    );

    socket.on("tracking:eta", (data: { eta: number }) => {
      useTrackingStore.getState().setEta(data.eta);
    });
  }

  return socket;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function connectSocket(): void {
  const s = getSocket();
  if (!s.connected) {
    s.connect();
  }
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
    useTrackingStore.getState().setConnected(false);
  }
}

export function joinJobRoom(jobId: string): void {
  const s = getSocket();
  s.emit("tracking:join", { jobId });
  useTrackingStore.getState().setJobId(jobId);
}

export function leaveJobRoom(jobId: string): void {
  const s = getSocket();
  s.emit("tracking:leave", { jobId });
}

export { socket };
