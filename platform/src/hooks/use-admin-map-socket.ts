"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:5001";

interface ContractorLocationUpdate {
  contractor_id: string;
  lat: number;
  lng: number;
}

interface JobStatusUpdate {
  job_id: string;
  status: string;
}

interface UseAdminMapSocketOptions {
  onContractorLocation?: (data: ContractorLocationUpdate) => void;
  onJobStatus?: (data: JobStatusUpdate) => void;
}

export function useAdminMapSocket(options: UseAdminMapSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  // Use refs for callbacks to avoid socket recreation when callbacks change
  const onContractorLocationRef = useRef(options.onContractorLocation);
  onContractorLocationRef.current = options.onContractorLocation;

  const onJobStatusRef = useRef(options.onJobStatus);
  onJobStatusRef.current = options.onJobStatus;

  useEffect(() => {
    const socket = io(WS_URL, {
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      transports: ["websocket", "polling"],
    });
    socketRef.current = socket;

    socket.on("connect", () => {
      setIsConnected(true);
      socket.emit("admin:join");
    });

    socket.on("disconnect", () => {
      setIsConnected(false);
    });

    socket.on("connect_error", () => {
      setIsConnected(false);
    });

    socket.on("admin:contractor-location", (data: ContractorLocationUpdate) => {
      onContractorLocationRef.current?.(data);
    });

    socket.on("admin:job-status", (data: JobStatusUpdate) => {
      onJobStatusRef.current?.(data);
    });

    return () => {
      socket.emit("admin:leave");
      socket.disconnect();
      socketRef.current = null;
      setIsConnected(false);
    };
  }, []);

  return { isConnected };
}
