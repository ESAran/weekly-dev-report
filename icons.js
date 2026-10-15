const paths = {
  layers: '<path fill="currentColor" stroke="none" d="m12 2 10 5-10 5L2 7Zm-10 9 10 5 10-5v3l-10 5-10-5Zm0 6 10 5 10-5v3l-10 5-10-5Z" transform="translate(0 -1) scale(1 .92)"/>',
  target: '<circle cx="11" cy="13" r="9"/><circle cx="11" cy="13" r="5" fill="currentColor" stroke="none"/><path d="m18 6 3-3m-3 0 3 3"/>',
  code: '<path d="m7 6-5 6 5 6m10-12 5 6-5 6m-3-14-4 16"/>',
  branch: '<circle cx="6" cy="4" r="2.3"/><circle cx="6" cy="20" r="2.3"/><circle cx="18" cy="8" r="2.3"/><path d="M6 7v10m0-4c8 0 12 0 12-3"/>',
  bars: '<rect x="2" y="13" width="4" height="9" rx="1.1" fill="currentColor" stroke="none"/><rect x="10" y="3" width="4" height="19" rx="1.1" fill="currentColor" stroke="none"/><rect x="18" y="8" width="4" height="14" rx="1.1" fill="currentColor" stroke="none"/>',
  pie: '<path d="M11 2a10 10 0 1 0 11 11H11Z" fill="currentColor" stroke="none"/><path d="M14 1v9h9a10 10 0 0 0-9-9Z" fill="currentColor" stroke="none"/>',
  document: '<path d="M5 2h10l5 5v15H5Z" fill="currentColor" stroke="none"/><path d="M15 2v6h5M8 11h9M8 15h9M8 19h9" stroke="#142a40" stroke-width="1.6"/>',
  cube: '<path d="m12 2 10 6v12l-10 6-10-6V8Zm0 12L2 8m10 6L22 8M12 14v12" transform="translate(2 -1) scale(.84)"/>',
  monitor: '<rect x="2" y="3" width="20" height="15" rx="1"/><path d="M12 18v4m-5 0h10"/>',
  phone: '<rect x="5" y="1" width="14" height="22" rx="2"/><circle cx="12" cy="19" r=".8" fill="currentColor" stroke="none"/>',
  globe: '<circle cx="12" cy="12" r="10.5"/><ellipse cx="12" cy="12" rx="4.5" ry="10.5"/><path d="M2 12h20"/>',
  bulb: '<path d="M8 17c0-3-4-4-4-9a8 8 0 0 1 16 0c0 5-4 6-4 9Z" fill="currentColor" stroke="none"/><path d="M9 19h6m-5 3h4"/>',
  people: '<circle cx="8" cy="6" r="3.4" fill="currentColor" stroke="none"/><circle cx="18" cy="6" r="3.4" fill="currentColor" stroke="none"/><path d="M1 21v-4c0-6 14-6 14 0v4Zm15 0v-4a7 7 0 0 0-2-5c6-2 10 1 10 5v4Z" fill="currentColor" stroke="none"/>',
  chevron: '<path d="m8 4 8 8-8 8"/>',
  github: '<path fill="currentColor" stroke="none" d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.23c-3.34.73-4.04-1.42-4.04-1.42-.55-1.39-1.34-1.76-1.34-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.49.99.11-.78.42-1.3.76-1.6-2.67-.31-5.47-1.34-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.25 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.62-5.49 5.92.43.37.81 1.1.81 2.22v3.3c0 .32.22.7.83.58A12 12 0 0 0 12 .5Z"/>',
  gitlab: '<path fill="#e24329" stroke="none" d="m12 23 4.4-13.5H7.6Z"/><path fill="#fc6d26" stroke="none" d="m12 23-4.4-13.5H1.5Zm0 0 4.4-13.5h6.1Z"/><path fill="#fca326" stroke="none" d="M1.5 9.5.1 14a1.2 1.2 0 0 0 .45 1.35L12 23Zm21 0 1.4 4.5a1.2 1.2 0 0 1-.45 1.35L12 23Z"/><path fill="#e24329" stroke="none" d="m1.5 9.5 2.8-8.6a.55.55 0 0 1 1.05 0L7.6 9.5Zm14.9 0L18.65.9a.55.55 0 0 1 1.05 0l2.8 8.6Z"/>'
};

export function icon(name, className = '') {
  return `<svg class="icon ${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.cube}</svg>`;
}
