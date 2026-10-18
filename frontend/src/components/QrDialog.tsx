import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { useT } from '../i18n'
import { Dialog } from './AccountDialogs'

// A QR code that opens the published site: to print for café tables, a shop
// window or flyers. Made here in the browser — nothing is sent anywhere.
export default function QrDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const t = useT()
  const [image, setImage] = useState<string | null>(null)

  useEffect(() => {
    // Big enough to print sharply at any size people actually use.
    QRCode.toDataURL(url, { width: 1024, margin: 2, errorCorrectionLevel: 'M' })
      .then(setImage)
      .catch(() => setImage(null))
  }, [url])

  const slug = url.split('/').pop() || 'site'

  return (
    <Dialog title={t('qr.title')} onClose={onClose}>
      <div className="qr">
        {image ? <img className="qr__image" src={image} alt={t('qr.alt', { url })} /> : <div className="qr__image" />}
        <p className="dialog__text">{t('qr.hint')}</p>
      </div>
      <div className="dialog__actions">
        <button type="button" className="btn" onClick={onClose}>
          {t('gallery.close')}
        </button>
        {image && (
          <a className="btn btn--blue" href={image} download={`vibeforge-qr-${slug}.png`}>
            {t('qr.download')}
          </a>
        )}
      </div>
    </Dialog>
  )
}
