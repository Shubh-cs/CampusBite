import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { createOwnerMenuItem, fetchOwnerMenuItems, updateOwnerMenuItem } from '../api/ownerMenu.js';
import { fetchOwnerRestaurant } from '../api/ownerOrders.js';
import { Pagination } from '../components/Pagination.jsx';
import { formatINR } from '../context/CartContext.jsx';

const PAGE_SIZE = 10;
const EMPTY_FORM = { name: '', description: '', category: '', price: '', image_url: '' };

function validateForm(form) {
  const errors = {};
  if (!form.name.trim()) errors.name = 'Enter a dish name.';
  else if (form.name.trim().length > 160) errors.name = 'Dish names can be at most 160 characters.';
  if (!form.category.trim()) errors.category = 'Enter a category.';
  else if (form.category.trim().length > 80) errors.category = 'Categories can be at most 80 characters.';
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(form.price) || Number(form.price) <= 0) {
    errors.price = 'Enter a positive price with no more than two decimal places.';
  }
  if (form.image_url.trim()) {
    try {
      const imageUrl = new URL(form.image_url.trim());
      if (!['http:', 'https:'].includes(imageUrl.protocol) || form.image_url.trim().length > 2048) {
        errors.image_url = 'Enter an HTTP or HTTPS image URL up to 2048 characters.';
      }
    } catch {
      errors.image_url = 'Enter a valid HTTP or HTTPS image URL.';
    }
  }
  return errors;
}

function formFromItem(item) {
  return {
    name: item.name,
    description: item.description || '',
    category: item.category,
    price: String(item.price),
    image_url: item.image_url || '',
  };
}

export function OwnerMenuPage() {
  const [page, setPage] = useState(1);
  const [result, setResult] = useState(null);
  const [restaurant, setRestaurant] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingItem, setEditingItem] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [busyItemId, setBusyItemId] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [actionError, setActionError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [retryKey, setRetryKey] = useState(0);

  const loadMenu = useCallback(async (targetPage = page) => {
    setIsLoading(true);
    setLoadError('');
    try {
      const [menuPage, ownerRestaurant] = await Promise.all([
        fetchOwnerMenuItems(targetPage, PAGE_SIZE),
        fetchOwnerRestaurant(),
      ]);
      setResult(menuPage);
      setRestaurant(ownerRestaurant);
    } catch (error) {
      setLoadError(error.message || 'Your restaurant menu could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  }, [page]);

  useEffect(() => { void loadMenu(); }, [loadMenu, retryKey]);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setActionError('');
    setSuccessMessage('');
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingItem(null);
    setFieldErrors({});
    setActionError('');
  }

  async function submitForm(event) {
    event.preventDefault();
    if (isSaving || busyItemId !== null) return;
    const errors = validateForm(form);
    setFieldErrors(errors);
    setActionError('');
    setSuccessMessage('');
    if (Object.keys(errors).length) return;

    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      category: form.category.trim(),
      price: form.price,
      image_url: form.image_url.trim() || null,
    };

    setIsSaving(true);
    try {
      if (editingItem) {
        await updateOwnerMenuItem(editingItem.id, payload);
        setSuccessMessage(`${payload.name} was updated.`);
        resetForm();
        await loadMenu(page);
      } else {
        await createOwnerMenuItem(payload);
        const newPage = Math.max(1, Math.ceil(((result?.total || 0) + 1) / PAGE_SIZE));
        setSuccessMessage(`${payload.name} was added to your menu.`);
        resetForm();
        if (newPage === page) await loadMenu(newPage);
        else setPage(newPage);
      }
    } catch (error) {
      setActionError(error.message || 'The dish could not be saved. Please try again.');
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleAvailability(item) {
    if (isSaving || busyItemId !== null) return;
    setBusyItemId(item.id);
    setActionError('');
    setSuccessMessage('');
    try {
      await updateOwnerMenuItem(item.id, { is_available: !item.is_available });
      setSuccessMessage(`${item.name} is now ${item.is_available ? 'unavailable' : 'available'}.`);
      await loadMenu(page);
    } catch (error) {
      setActionError(error.message || 'Availability could not be updated. Please try again.');
    } finally {
      setBusyItemId(null);
    }
  }

  function beginEdit(item) {
    setEditingItem(item);
    setForm(formFromItem(item));
    setFieldErrors({});
    setActionError('');
    setSuccessMessage('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <main className="discovery-page owner-menu-page">
      <Link className="back-link" to="/account/owner">← Owner dashboard</Link>
      <p className="eyebrow">Menu management</p>
      <h1 className="cart-title">{restaurant?.name || 'Your menu'}</h1>

      <section className="owner-menu-form-card" aria-labelledby="owner-menu-form-title">
        <p className="card-kicker">Restaurant menu</p>
        <h2 id="owner-menu-form-title">{editingItem ? `Edit ${editingItem.name}` : 'Add a dish'}</h2>
        <form className="owner-menu-form" onSubmit={submitForm} noValidate>
          <label className="form-field">
            <span>Dish name</span>
            <input required maxLength={160} value={form.name} onChange={(event) => updateField('name', event.target.value)} aria-invalid={Boolean(fieldErrors.name)} />
            {fieldErrors.name && <small className="owner-menu-field-error">{fieldErrors.name}</small>}
          </label>
          <label className="form-field">
            <span>Category</span>
            <input required maxLength={80} value={form.category} onChange={(event) => updateField('category', event.target.value)} aria-invalid={Boolean(fieldErrors.category)} />
            {fieldErrors.category && <small className="owner-menu-field-error">{fieldErrors.category}</small>}
          </label>
          <label className="form-field">
            <span>Price (INR)</span>
            <input required type="number" min="0.01" max="99999999.99" step="0.01" inputMode="decimal" value={form.price} onChange={(event) => updateField('price', event.target.value)} aria-invalid={Boolean(fieldErrors.price)} />
            {fieldErrors.price && <small className="owner-menu-field-error">{fieldErrors.price}</small>}
          </label>
          <label className="form-field owner-menu-wide-field">
            <span>Description <small>(optional)</small></span>
            <textarea rows="3" value={form.description} onChange={(event) => updateField('description', event.target.value)} />
          </label>
          <label className="form-field owner-menu-wide-field">
            <span>Image URL <small>(optional)</small></span>
            <input type="url" maxLength={2048} value={form.image_url} onChange={(event) => updateField('image_url', event.target.value)} aria-invalid={Boolean(fieldErrors.image_url)} />
            {fieldErrors.image_url && <small className="owner-menu-field-error">{fieldErrors.image_url}</small>}
          </label>
          {actionError && <p className="form-message form-message--error owner-menu-form-message" role="alert">{actionError}</p>}
          {successMessage && <p className="form-message owner-menu-success" role="status">{successMessage}</p>}
          <div className="owner-menu-form-actions">
            <button className="form-submit" type="submit" disabled={isSaving || busyItemId !== null}>
              {isSaving ? 'Saving…' : editingItem ? 'Save changes' : 'Add dish'}
            </button>
            {editingItem && <button className="secondary-button" type="button" disabled={isSaving || busyItemId !== null} onClick={resetForm}>Cancel edit</button>}
          </div>
        </form>
      </section>

      <section className="owner-orders-section owner-menu-list" aria-labelledby="owner-menu-list-title">
        <div className="section-heading">
          <div><p className="card-kicker">All dishes</p><h2 id="owner-menu-list-title">Your menu</h2></div>
          {result && <span className="result-count">{result.total} total</span>}
        </div>
        {loadError && <section className="state-panel state-panel--error" role="alert"><p>{loadError}</p><button className="secondary-button" type="button" onClick={() => setRetryKey((key) => key + 1)}>Retry</button></section>}
        {actionError && <p className="form-message form-message--error" role="alert">{actionError}</p>}
        {isLoading && <p className="state-panel" role="status">Loading your menu…</p>}
        {!isLoading && !loadError && result?.items.length === 0 && <p className="state-panel">Your menu is empty. Add a dish using the form above.</p>}
        {!isLoading && result?.items.length > 0 && <>
          <div className="owner-menu-items">
            {result.items.map((item) => (
              <article className="owner-menu-item" key={item.id}>
                <div className="owner-menu-item-copy">
                  <div className="owner-menu-item-heading">
                    <div><p className="card-kicker">{item.category}</p><h3>{item.name}</h3></div>
                    <span className={`owner-menu-availability${item.is_available ? '' : ' is-unavailable'}`}>{item.is_available ? 'Available' : 'Unavailable'}</span>
                  </div>
                  {item.description && <p className="card-description">{item.description}</p>}
                  <p className="owner-menu-item-meta">{formatINR(String(item.price))}{item.image_url && <span> · Image URL set</span>}</p>
                </div>
                <div className="owner-menu-item-actions">
                  <button className="secondary-button" type="button" disabled={isSaving || busyItemId !== null} onClick={() => beginEdit(item)}>Edit</button>
                  <button className="secondary-button" type="button" disabled={isSaving || busyItemId !== null} onClick={() => void toggleAvailability(item)}>
                    {busyItemId === item.id ? 'Saving…' : item.is_available ? 'Mark unavailable' : 'Mark available'}
                  </button>
                </div>
              </article>
            ))}
          </div>
          <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPageChange={(nextPage) => { resetForm(); setPage(nextPage); }} />
        </>}
      </section>
    </main>
  );
}
