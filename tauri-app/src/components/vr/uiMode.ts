import { createContext, useContext } from 'react'

/** Which UI a label should use. In an immersive session only WebGL is visible, so text must be
 * in-world geometry; on a desktop monitor that same geometry is a few pixels tall, so labels
 * render as crisp screen-space HTML instead. */
export const UIMode = createContext<{ inXR: boolean }>({ inXR: false })

export function useInXR(): boolean {
  return useContext(UIMode).inXR
}
