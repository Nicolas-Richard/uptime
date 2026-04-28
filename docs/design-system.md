# Design System — Tailwind Class Reference

Consistent utility classes used across the Uptime app. Copy these directly into templates.

## Buttons

| Token | Classes |
|---|---|
| Primary | `bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg` |
| Secondary / Outline | `border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium px-4 py-2 rounded-lg` |
| Danger | `bg-red-600 hover:bg-red-700 text-white font-medium px-4 py-2 rounded-lg` |

## Status Badges

| Token | Classes |
|---|---|
| Up | `bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded-full` |
| Down | `bg-red-100 text-red-800 text-xs font-medium px-2.5 py-0.5 rounded-full` |
| Unknown | `bg-gray-100 text-gray-800 text-xs font-medium px-2.5 py-0.5 rounded-full` |

## Card Container

```
bg-white rounded-lg shadow-sm border border-gray-200 p-4
```

## Table

```html
<table class="min-w-full divide-y divide-gray-200">
  <thead class="bg-gray-50">
    <tr>
      <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">...</th>
    </tr>
  </thead>
  <tbody class="bg-white divide-y divide-gray-200">
    <tr>
      <td class="px-4 py-3 text-sm text-gray-900">...</td>
    </tr>
  </tbody>
</table>
```

Wrap tables in `<div class="overflow-x-auto">` for responsive horizontal scroll.

## Form Inputs

```
w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
```

## Typography

| Element | Classes |
|---|---|
| Page heading | `text-2xl font-bold text-gray-900` |
| Section heading | `text-lg font-semibold text-gray-900` |
| Body text | `text-sm text-gray-600` |
