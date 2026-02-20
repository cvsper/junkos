"use client";

import { useEffect, useState, useCallback } from "react";
import { useSocket } from "@/lib/socket-provider";

interface JobNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  data?: Record<string, unknown>;
  timestamp: Date;
  read: boolean;
}

export function useJobNotifications() {
  const { socket } = useSocket();
  const [notifications, setNotifications] = useState<JobNotification[]>([]);

  useEffect(() => {
    if (!socket) return;

    const handleJobStatus = (data: { job_id: string; status: string }) => {
      setNotifications((prev) => [
        {
          id: crypto.randomUUID(),
          type: "job_status",
          title: `Job ${data.status.replace("_", " ")}`,
          body: `Job status updated to ${data.status}`,
          data,
          timestamp: new Date(),
          read: false,
        },
        ...prev,
      ]);
    };

    const handleNewJob = (data: { job_id: string; address?: string }) => {
      setNotifications((prev) => [
        {
          id: crypto.randomUUID(),
          type: "new_job",
          title: "New Job Available",
          body: data.address
            ? `New job at ${data.address}`
            : "A new job is available nearby",
          data,
          timestamp: new Date(),
          read: false,
        },
        ...prev,
      ]);
    };

    const handleJobAccepted = (data: { job_id: string }) => {
      setNotifications((prev) => [
        {
          id: crypto.randomUUID(),
          type: "job_accepted",
          title: "Job Accepted",
          body: "A driver has accepted the job",
          data,
          timestamp: new Date(),
          read: false,
        },
        ...prev,
      ]);
    };

    socket.on("job:status", handleJobStatus);
    socket.on("job:new", handleNewJob);
    socket.on("job:accepted", handleJobAccepted);

    return () => {
      socket.off("job:status", handleJobStatus);
      socket.off("job:new", handleNewJob);
      socket.off("job:accepted", handleJobAccepted);
    };
  }, [socket]);

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return { notifications, unreadCount, markAsRead, markAllAsRead };
}
