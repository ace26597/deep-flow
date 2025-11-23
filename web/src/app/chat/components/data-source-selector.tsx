"use client";

import { Database, Check, ChevronsUpDown, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "~/components/ui/button";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "~/components/ui/command";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "~/components/ui/popover";
import {
    setDataSources,
    setSelectedResources,
    useSettingsStore,
} from "~/core/store";
import { cn } from "~/lib/utils";

export function DataSourceSelector() {
    const [open, setOpen] = useState(false);
    const dataSources = useSettingsStore((state) => state.general.dataSources);
    const selectedResources = useSettingsStore(
        (state) => state.general.selectedResources || [],
    );

    const [ragResources, setRagResources] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (dataSources.includes("mongodb")) {
            setIsLoading(true);
            fetch("/api/rag/resources")
                .then((res) => res.json())
                .then((data) => {
                    setRagResources(data);
                    setIsLoading(false);
                })
                .catch(() => {
                    setIsLoading(false);
                });
        } else {
            setRagResources(null);
        }
    }, [dataSources]);

    const toggleDataSource = (source: string) => {
        const newDataSources = dataSources.includes(source)
            ? dataSources.filter((s) => s !== source)
            : [...dataSources, source];
        setDataSources(newDataSources);
    };

    const toggleResource = (resourceUri: string) => {
        const newResources = selectedResources.includes(resourceUri)
            ? selectedResources.filter((r) => r !== resourceUri)
            : [...selectedResources, resourceUri];
        setSelectedResources(newResources);
    };

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className="justify-between rounded-2xl"
                >
                    <Database className="mr-2 h-4 w-4" />
                    Data Sources
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[300px] p-0">
                <Command>
                    <CommandInput placeholder="Search sources..." />
                    <CommandList>
                        <CommandEmpty>No sources found.</CommandEmpty>
                        <CommandGroup heading="Providers">
                            {["tavily", "mongodb", "pubmed", "arxiv"].map((source) => (
                                <CommandItem
                                    key={source}
                                    value={source}
                                    onSelect={() => toggleDataSource(source)}
                                >
                                    <Check
                                        className={cn(
                                            "mr-2 h-4 w-4",
                                            dataSources.includes(source) ? "opacity-100" : "opacity-0",
                                        )}
                                    />
                                    <span className="capitalize">{source}</span>
                                </CommandItem>
                            ))}
                        </CommandGroup>
                        {dataSources.includes("mongodb") && (
                            <CommandGroup heading="MongoDB Collections">
                                {isLoading ? (
                                    <div className="flex items-center justify-center p-2">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    </div>
                                ) : (
                                    ragResources?.resources?.map((resource: any) => (
                                        <CommandItem
                                            key={resource.uri}
                                            value={resource.title}
                                            onSelect={() => toggleResource(resource.uri)}
                                        >
                                            <Check
                                                className={cn(
                                                    "mr-2 h-4 w-4",
                                                    selectedResources.includes(resource.uri)
                                                        ? "opacity-100"
                                                        : "opacity-0",
                                                )}
                                            />
                                            {resource.title}
                                        </CommandItem>
                                    ))
                                )}
                                {!isLoading && ragResources?.resources?.length === 0 && (
                                    <div className="p-2 text-sm text-muted-foreground text-center">
                                        No collections found.
                                    </div>
                                )}
                            </CommandGroup>
                        )}
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
