import { request } from "./client";

export type Playlist = {
  shown: boolean;
  offline: boolean;
  title: string | null;
  genre: string | null;
  artwork_url: string | null;
  permalink_url: string | null;
};

export function getPlaylist() {
  return request<Playlist>("/playlist");
}
