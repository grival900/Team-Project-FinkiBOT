import { useState } from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { cn } from "@/lib/utils";
import type { CourseCodeOption } from "@/lib/api";

// pick from real course codes instead of typing, to avoid typos
export function CourseCodeCombobox({
  values,
  onChange,
  options,
  placeholder,
  emptyLabel,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  options: CourseCodeOption[];
  placeholder: string;
  emptyLabel: string;
}) {
  const [open, setOpen] = useState(false);
  const byCode = new Map(options.map((o) => [o.code, o]));

  function toggle(code: string) {
    onChange(values.includes(code) ? values.filter((c) => c !== code) : [...values, code]);
  }

  return (
    <div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring"
          >
            <span className="text-muted-foreground">{placeholder}</span>
            <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-0" align="start">
          <Command>
            <CommandInput placeholder={placeholder} />
            <CommandList>
              <CommandEmpty>{emptyLabel}</CommandEmpty>
              <CommandGroup>
                {options.map((o) => (
                  <CommandItem key={o.code} value={`${o.code} ${o.name}`} onSelect={() => toggle(o.code)}>
                    <Check className={cn("size-4", values.includes(o.code) ? "opacity-100" : "opacity-0")} />
                    <span className="flex-1 truncate">{o.name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{o.code}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {values.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((code) => (
            <span
              key={code}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-accent px-2.5 py-0.5 text-xs text-accent-foreground"
            >
              {byCode.get(code)?.name ?? code}
              <button type="button" onClick={() => toggle(code)}>
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
