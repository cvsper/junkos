// IndexedDB preserves File objects across reloads. Every record is scoped to
// an account (or this browser's guest draft); payment card data never enters it.
const DATABASE = "umuve-browser-work";
const STORE = "drafts";
const writes = new Map<string, Promise<void>>();

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("This browser cannot save your work. Keep this page open."));
      return;
    }
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("Close other Umuve tabs and try saving again."));
  });
}

export async function readBrowserWork<T>(key: string): Promise<T | null> {
  await writes.get(key)?.catch(() => undefined);
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const request = tx.objectStore(STORE).get(key);
    tx.oncomplete = () => { db.close(); resolve(request.result ?? null); };
    tx.onabort = tx.onerror = () => { db.close(); reject(tx.error); };
  });
}

function write(key: string, value: unknown, remove: boolean): Promise<void> {
  const previous = writes.get(key) ?? Promise.resolve();
  const next = previous.catch(() => undefined).then(async () => {
    const db = await openDatabase();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      if (remove) tx.objectStore(STORE).delete(key);
      else tx.objectStore(STORE).put(value, key);
      tx.oncomplete = () => { db.close(); resolve(); };
      tx.onabort = tx.onerror = () => { db.close(); reject(tx.error); };
    });
  });
  writes.set(key, next);
  // Attach both handlers so cleanup does not create an unhandled rejection.
  void next.then(() => { if (writes.get(key) === next) writes.delete(key); }, () => {
    if (writes.get(key) === next) writes.delete(key);
  });
  return next;
}

export const saveBrowserWork = (key: string, value: unknown) => write(key, value, false);
export const removeBrowserWork = (key: string) => write(key, undefined, true);
export const bookingDraftKey = (userId?: string | null) => `booking:${userId ? `user:${userId}` : "guest"}`;

export function serviceDate(offset = 0): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((p) => p.type === type)!.value;
  const day = new Date(`${part("year")}-${part("month")}-${part("day")}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + offset);
  return day.toISOString().slice(0, 10);
}
