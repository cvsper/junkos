export function payoutStatusLabel(status?: string | null): string {
  switch (status) {
    case "paid": return "Paid";
    case "processing": return "Processing";
    case "pending": return "Pending payout";
    case "pending_connect": return "Finish payout setup";
    case "failed": return "Payout needs attention";
    default: return "Check earnings for payout status";
  }
}
