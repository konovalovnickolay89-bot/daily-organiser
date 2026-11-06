import { useEffect, useState } from "react";
import { getPlaylist, type Playlist } from "../../api/playlist";
import { useHouseTick } from "../../house/HouseContext";

/**
 * The latest hearthis.at track, as a link. Nothing is streamed in the app.
 * Hidden until a playlist source is set. Offline, it stays quiet.
 */
export function QuietSuggestion() {
  const tick = useHouseTick();
  const [track, setTrack] = useState<Playlist | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPlaylist()
      .then((data) => {
        if (!cancelled) setTrack(data);
      })
      .catch(() => {
        if (!cancelled) setTrack({ shown: true, offline: true, title: null, genre: null, artwork_url: null, permalink_url: null });
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  if (!track?.shown) return null;

  const quiet = track.offline && !track.title;
  return (
    <aside
      className="quiet-suggestion serif mt-8 max-w-[22rem] text-left text-base font-normal leading-snug text-cream-dim"
      data-module="quiet-media"
      aria-label="Later"
    >
      <p className="mb-2 font-sans text-xs font-medium uppercase not-italic tracking-[0.16em] text-cream-dim">Later</p>
      {quiet || !track.permalink_url ? (
        <p className="m-0 italic">The playlist is quiet right now.</p>
      ) : (
        <a
          className="calm mt-2 flex min-h-11 items-center gap-4 text-inherit no-underline"
          href={track.permalink_url}
          target="_blank"
          rel="noopener noreferrer"
          data-playlist="track"
        >
          {track.artwork_url && (
            <img
              className="h-11 w-11 shrink-0 rounded-house object-cover"
              src={track.artwork_url}
              alt=""
              width={44}
              height={44}
            />
          )}
          <span className="min-w-0">
            <span className="block truncate font-medium not-italic text-cream">{track.title}</span>
            {track.genre && <span className="block truncate text-sm italic text-cream-dim">{track.genre}</span>}
          </span>
        </a>
      )}
    </aside>
  );
}
