import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { fetchRestaurantMenu } from '../api/catalog.js';

export const CART_STORAGE_KEY = 'campusbite_cart';
const CART_VERSION = 1;
const EMPTY_FILTERS = { search: '', minPrice: '', maxPrice: '' };

const CartContext = createContext(null);

function emptyCart() {
  return { restaurantId: null, restaurantName: '', items: [] };
}

function validPrice(value) {
  return typeof value === 'string' && /^\d{1,8}(\.\d{1,2})?$/.test(value);
}

function readCart() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) || 'null');
    if (
      !stored || stored.version !== CART_VERSION || !Number.isSafeInteger(stored.restaurantId)
      || stored.restaurantId <= 0 || !Array.isArray(stored.items)
    ) return emptyCart();

    const items = stored.items.flatMap((item) => {
      if (
        !Number.isSafeInteger(item.menuItemId) || item.menuItemId <= 0
        || !Number.isSafeInteger(item.quantity) || item.quantity < 1
        || typeof item.name !== 'string' || !validPrice(item.unitPrice)
      ) return [];
      return [{
        menuItemId: item.menuItemId,
        name: item.name,
        quantity: item.quantity,
        unitPrice: item.unitPrice,
        currentUnitPrice: null,
        availability: 'checking',
      }];
    });

    return items.length
      ? { restaurantId: stored.restaurantId, restaurantName: String(stored.restaurantName || ''), items }
      : emptyCart();
  } catch {
    return emptyCart();
  }
}

function priceToPaise(value) {
  const [rupees, fraction = ''] = String(value).split('.');
  return Number(rupees) * 100 + Number(fraction.padEnd(2, '0'));
}

export function formatINR(value) {
  const paise = typeof value === 'number' ? value : priceToPaise(value);
  const rupees = Math.floor(paise / 100);
  const fraction = String(paise % 100).padStart(2, '0');
  return `₹${rupees.toLocaleString('en-IN')}.${fraction}`;
}

export function itemSubtotalPaise(item) {
  return priceToPaise(item.unitPrice) * item.quantity;
}

async function loadCurrentMenu(restaurantId) {
  const items = new Map();
  let page = 1;
  let pageCount = 1;

  while (page <= pageCount) {
    const result = await fetchRestaurantMenu(restaurantId, EMPTY_FILTERS, page);
    for (const item of result.items) items.set(item.id, item);
    pageCount = Math.max(1, Math.ceil(result.total / result.page_size));
    page += 1;
  }
  return items;
}

export function CartProvider({ children }) {
  const [cart, setCart] = useState(readCart);
  const cartRef = useRef(cart);
  cartRef.current = cart;
  const [isRevalidating, setIsRevalidating] = useState(() => readCart().items.length > 0);
  const [revalidationError, setRevalidationError] = useState('');
  const [storageError, setStorageError] = useState('');

  useEffect(() => {
    if (!cart.items.length) {
      setIsRevalidating(false);
      setRevalidationError('');
      return;
    }

    let active = true;
    setIsRevalidating(true);
    setRevalidationError('');
    const restaurantId = cart.restaurantId;

    loadCurrentMenu(restaurantId)
      .then((currentItems) => {
        if (!active) return;
        setCart((currentCart) => {
          if (currentCart.restaurantId !== restaurantId) return currentCart;
          return {
            ...currentCart,
            items: currentCart.items.map((cartItem) => {
              const currentItem = currentItems.get(cartItem.menuItemId);
              if (!currentItem) return { ...cartItem, availability: 'unavailable', currentUnitPrice: null };
              const currentUnitPrice = String(currentItem.price);
              return {
                ...cartItem,
                name: currentItem.name,
                availability: 'available',
                currentUnitPrice: currentUnitPrice === cartItem.unitPrice ? null : currentUnitPrice,
              };
            }),
          };
        });
      })
      .catch((error) => {
        if (!active || cartRef.current.restaurantId !== restaurantId) return;
        setRevalidationError(error.message || 'The saved cart could not be checked against the current menu.');
        setCart((currentCart) => currentCart.restaurantId === restaurantId
          ? { ...currentCart, items: currentCart.items.map((item) => ({ ...item, availability: 'unverified' })) }
          : currentCart);
      })
      .finally(() => {
        if (active) setIsRevalidating(false);
      });

    return () => { active = false; };
  }, []);

  useEffect(() => {
    try {
      if (!cart.items.length) {
        window.localStorage.removeItem(CART_STORAGE_KEY);
      } else {
        window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify({
          version: CART_VERSION,
          restaurantId: cart.restaurantId,
          restaurantName: cart.restaurantName,
          items: cart.items.map(({ menuItemId, name, quantity, unitPrice }) => ({
            menuItemId, name, quantity, unitPrice,
          })),
        }));
      }
      setStorageError('');
    } catch {
      setStorageError('Your cart is available for this visit, but your browser could not save it for later.');
    }
  }, [cart]);

  const addItem = useCallback((restaurant, item) => {
    if (cart.restaurantId && cart.restaurantId !== restaurant.id) {
      return { requiresReplacement: true };
    }
    setRevalidationError('');
    setCart((currentCart) => {
      if (currentCart.restaurantId && currentCart.restaurantId !== restaurant.id) return currentCart;
      const existing = currentCart.items.find((line) => line.menuItemId === item.id);
      if (existing) {
        return {
          ...currentCart,
          restaurantName: restaurant.name,
          items: currentCart.items.map((line) => line.menuItemId === item.id
            ? {
              ...line,
              quantity: line.quantity + 1,
              currentUnitPrice: String(item.price) === line.unitPrice ? null : String(item.price),
              availability: 'available',
            }
            : line),
        };
      }
      return {
        restaurantId: restaurant.id,
        restaurantName: restaurant.name,
        items: [...currentCart.items, {
          menuItemId: item.id,
          name: item.name,
          quantity: 1,
          unitPrice: String(item.price),
          currentUnitPrice: null,
          availability: 'available',
        }],
      };
    });
    return { requiresReplacement: false };
  }, [cart.restaurantId]);

  const replaceCartWithItem = useCallback((restaurant, item) => {
    setRevalidationError('');
    setIsRevalidating(false);
    setCart({
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      items: [{
        menuItemId: item.id,
        name: item.name,
        quantity: 1,
        unitPrice: String(item.price),
        currentUnitPrice: null,
        availability: 'available',
      }],
    });
  }, []);

  const increaseQuantity = useCallback((menuItemId) => {
    setCart((currentCart) => ({
      ...currentCart,
      items: currentCart.items.map((item) => item.menuItemId === menuItemId
        ? { ...item, quantity: item.quantity + 1 }
        : item),
    }));
  }, []);

  const decreaseQuantity = useCallback((menuItemId) => {
    setCart((currentCart) => ({
      ...currentCart,
      items: currentCart.items.map((item) => item.menuItemId === menuItemId
        ? { ...item, quantity: Math.max(1, item.quantity - 1) }
        : item),
    }));
  }, []);

  const removeItem = useCallback((menuItemId) => {
    if (cart.items.length === 1 && cart.items[0].menuItemId === menuItemId) {
      setIsRevalidating(false);
      setRevalidationError('');
    }
    setCart((currentCart) => {
      const items = currentCart.items.filter((item) => item.menuItemId !== menuItemId);
      return items.length ? { ...currentCart, items } : emptyCart();
    });
  }, [cart.items]);

  const acceptPriceChange = useCallback((menuItemId) => {
    setCart((currentCart) => ({
      ...currentCart,
      items: currentCart.items.map((item) => item.menuItemId === menuItemId && item.currentUnitPrice
        ? { ...item, unitPrice: item.currentUnitPrice, currentUnitPrice: null }
        : item),
    }));
  }, []);

  const itemCount = cart.items.reduce((count, item) => count + item.quantity, 0);
  const subtotalPaise = cart.items.reduce((total, item) => total + itemSubtotalPaise(item), 0);

  const value = useMemo(() => ({
    cart,
    itemCount,
    subtotalPaise,
    isRevalidating,
    revalidationError,
    storageError,
    addItem,
    replaceCartWithItem,
    increaseQuantity,
    decreaseQuantity,
    removeItem,
    acceptPriceChange,
  }), [
    cart, itemCount, subtotalPaise, isRevalidating, revalidationError, storageError,
    addItem, replaceCartWithItem, increaseQuantity, decreaseQuantity, removeItem, acceptPriceChange,
  ]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) throw new Error('useCart must be used inside CartProvider.');
  return context;
}
