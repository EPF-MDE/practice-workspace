import { AxiosError } from "axios";

export function errorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response)
      return "The workspace cannot be reached: your text is kept, try again.";
  }
  return "Sending failed: your text is kept, try again.";
}
