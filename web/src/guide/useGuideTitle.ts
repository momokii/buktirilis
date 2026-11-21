import { useEffect } from "react";

export function useGuideTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} — BuktiRilis guide` : "Guide — BuktiRilis";
    return () => {
      document.title = "BuktiRilis";
    };
  }, [title]);
}
