#!/bin/sh
# Instala KeyBio para tu usuario (sin permisos de administrador) y lo añade al menú de aplicaciones.
# Installs KeyBio for your user (no administrator rights) and adds it to the applications menu.
#
#   ./instalar.sh                 instalar o actualizar / install or update
#   ./instalar.sh --desinstalar   quitarlo (los perfiles se conservan) / remove it (profiles are kept)
#
# Lo copia tools/linux.py junto al programa empaquetado (KeyBio/instalar.sh).
set -eu

ID=io.github.ryt0n18.keybio
SRC=$(cd "$(dirname "$0")" && pwd)
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
DEST=$HOME/.local/opt/keybio
APPS=$DATA/applications
ICONS=$DATA/icons/hicolor
BIN=$HOME/.local/bin

refresh() {
    update-desktop-database "$APPS" 2>/dev/null || true
    gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true
}

uninstall() {
    rm -rf "$DEST"
    rm -f "$APPS/$ID.desktop"
    rm -f "$ICONS"/*/apps/"$ID.png"
    if [ -L "$BIN/keybio" ]; then rm -f "$BIN/keybio"; fi
    refresh
    echo "KeyBio desinstalado. Tus perfiles siguen en $DATA/keybio (bórrala si ya no los quieres)."
    echo "KeyBio uninstalled. Your profiles are still in $DATA/keybio (delete it if you no longer need them)."
}

case "${1:-}" in
    --desinstalar|--uninstall) uninstall; exit 0 ;;
    "") ;;
    *) echo "Uso / usage: $0 [--desinstalar]" >&2; exit 2 ;;
esac

if [ ! -x "$SRC/KeyBio" ] || [ ! -d "$SRC/linux" ]; then
    echo "Ejecuta este script desde la carpeta KeyBio descomprimida." >&2
    echo "Run this script from the extracted KeyBio folder." >&2
    exit 1
fi

# Copia el programa (si se ejecuta desde la copia ya instalada, no hace falta)
if [ "$SRC" != "$DEST" ]; then
    mkdir -p "$(dirname "$DEST")"
    rm -rf "$DEST.nuevo"
    cp -R "$SRC" "$DEST.nuevo"
    rm -rf "$DEST"
    mv "$DEST.nuevo" "$DEST"
fi

# Entrada del menú con la ruta real, iconos y «keybio» en el PATH
mkdir -p "$APPS"
sed -e "s|^Exec=.*|Exec=\"$DEST/KeyBio\"|" -e "s|^TryExec=.*|TryExec=$DEST/KeyBio|" \
    "$DEST/linux/$ID.desktop" > "$APPS/$ID.desktop"
for dir in "$DEST"/linux/icons/*/; do
    size=$(basename "$dir")
    mkdir -p "$ICONS/$size/apps"
    cp "$dir$ID.png" "$ICONS/$size/apps/$ID.png"
done
mkdir -p "$BIN"
ln -sf "$DEST/KeyBio" "$BIN/keybio"
refresh

echo "KeyBio instalado en $DEST. Ya aparece en el menú de aplicaciones."
echo "KeyBio installed in $DEST. It now appears in the applications menu."
if [ "$SRC" != "$DEST" ]; then
    echo "Puedes borrar la carpeta descomprimida. / You can delete the extracted folder."
fi
