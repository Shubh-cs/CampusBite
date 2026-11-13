export const ROLE_HOME_PATH = Object.freeze({
  CUSTOMER: '/restaurants',
  OWNER: '/account/owner',
  DELIVERY_PARTNER: '/account/delivery-partner',
});

export function roleHomePath(role) {
  return ROLE_HOME_PATH[role] || '/';
}
