/** Qué hay elegido de una lista, y cómo cambiarlo.
 *
 *  En su propio fichero: un módulo que exporta componentes y funciones a la
 *  vez rompe el refresco rápido de Vite, que es por lo que `useAuth` vive
 *  aparte desde el principio.
 */

import { useState } from 'react'

/** Qué hay elegido de una lista, y cómo cambiarlo.
 *
 *  Lo que desaparece de la lista deja de contar, y se poda **al leer**: con un
 *  efecto llegaría tarde y la barra diría «3 seleccionadas» de dos que quedan
 *  --- y peor, actuaría sobre una que ya se resolvió.
 */
export function useSelection(items, keyOf = (item) => item.id) {
  const [chosen, setChosen] = useState(() => new Set())

  const present = new Set(items.map(keyOf))
  const selected = [...chosen].filter((key) => present.has(key))
  const selectedSet = new Set(selected)

  return {
    selected,
    count: selected.length,
    isSelected: (item) => selectedSet.has(keyOf(item)),
    toggle: (item) =>
      setChosen((previous) => {
        const next = new Set(previous)
        const key = keyOf(item)
        if (next.has(key)) next.delete(key)
        else next.add(key)
        return next
      }),
    // Todo o nada, sobre lo que se está viendo: con un filtro puesto, «todo»
    // es lo filtrado. Marcar de golpe cosas que no están en pantalla es la
    // forma más rápida de aprobar algo sin haberlo visto.
    toggleAll: () => setChosen(selected.length === items.length ? new Set() : new Set(present)),
    clear: () => setChosen(new Set()),
    allSelected: items.length > 0 && selected.length === items.length,
    someSelected: selected.length > 0 && selected.length < items.length,
  }
}
