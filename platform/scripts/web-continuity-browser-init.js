// Test-only Stripe stand-in. Inject through agent-browser, never import into the app.
if (location.hostname === '127.0.0.1' && location.port === '3107') {
  window.Stripe = () => {
    let card;
    return {
      createToken: async () => ({}), createPaymentMethod: async () => ({}),
      confirmCardPayment: async () => ({ paymentIntent: { id: 'pi_local', status: 'succeeded' } }),
      paymentRequest: () => ({ canMakePayment: async () => null, on() {}, off() {} }),
      elements: () => ({
        update() {}, getElement: () => card,
        create: () => {
          const listeners = {};
          card = { on: (name, fn) => { listeners[name] = fn; }, off() {}, update() {}, destroy() {},
            mount: (target) => {
              const input = document.createElement('input');
              input.setAttribute('aria-label', 'Local test card');
              input.placeholder = 'Local test card (no charge)';
              input.style.cssText = 'width:100%;padding:12px;border:1px solid #ccc';
              input.addEventListener('input', () => listeners.change?.({ complete: input.value.length > 3 }));
              target.appendChild(input); listeners.ready?.();
            }
          }; return card;
        }
      })
    };
  };
}
