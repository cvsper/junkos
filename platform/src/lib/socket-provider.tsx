"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { io, Socket } from "socket.io-client";

const SOCKET_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://junkos-backend.onrender.com";

interface SocketContextValue {
  socket: Socket | null;
  isConnected: boolean;
  joinRoom: (room: string) => void;
  leaveRoom: (room: string) => void;
}

const SocketContext = createContext<SocketContextValue>({
  socket: null,
  isConnected: false,
  joinRoom: () => {},
  leaveRoom: () => {},
});

export function SocketProvider({
  children,
  token,
}: {
  children: ReactNode;
  token?: string;
}) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!token) return;

    const newSocket = io(SOCKET_URL, {
      auth: { token },
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 10,
    });

    newSocket.on("connect", () => setIsConnected(true));
    newSocket.on("disconnect", () => setIsConnected(false));

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [token]);

  const joinRoom = useCallback(
    (room: string) => {
      socket?.emit("join", { room });
    },
    [socket]
  );

  const leaveRoom = useCallback(
    (room: string) => {
      socket?.emit("leave", { room });
    },
    [socket]
  );

  return (
    <SocketContext.Provider value={{ socket, isConnected, joinRoom, leaveRoom }}>
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  return useContext(SocketContext);
}
