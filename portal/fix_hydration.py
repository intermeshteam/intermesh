import os

# 1. Fix topology/page.tsx
topo_path = os.path.expanduser('~/nexus/portal/src/app/(app)/topology/page.tsx')
if os.path.exists(topo_path):
    with open(topo_path, 'r', encoding='utf-8') as f:
        code = f.read()

    # Remplacer l'initialisation de l'heure
    code = code.replace("const [lastUpdate, setLastUpdate] = useState(nowTs());", "const [lastUpdate, setLastUpdate] = useState('');")
    code = code.replace("<span>{lastUpdate}</span>", "<span suppressHydrationWarning>{lastUpdate || '17:30:00'}</span>")
    code = code.replace("<span className=\"text-slate-600 shrink-0\">{l.ts}</span>", "<span className=\"text-slate-600 shrink-0\" suppressHydrationWarning>{l.ts}</span>")
    
    with open(topo_path, 'w', encoding='utf-8') as f:
        f.write(code)

# 2. Fix dashboard/page.tsx
dash_path = os.path.expanduser('~/nexus/portal/src/app/(app)/dashboard/page.tsx')
if os.path.exists(dash_path):
    with open(dash_path, 'r', encoding='utf-8') as f:
        code = f.read()

    code = code.replace("<span className=\"text-zinc-600 shrink-0\">{log.time.substring(0, 23)}Z</span>", "<span className=\"text-zinc-600 shrink-0\" suppressHydrationWarning>{log.time.substring(0, 23)}Z</span>")
    
    with open(dash_path, 'w', encoding='utf-8') as f:
        f.write(code)

print("✅ TOUS LES AVERTISSEMENTS D'HYDRATATION D'HORODATAGE ONT ÉTÉ CORRIGÉS !")
