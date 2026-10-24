import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import Register from '../Register';

function setup() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Register form validation', () => {
  it('shows per-field errors with accessible wiring', async () => {
    setup();
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    const name = screen.getByLabelText(/Full name/);
    expect(name).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('Choose your Mandal.')).toBeInTheDocument();
    expect(name.getAttribute('aria-describedby')).toBeTruthy();
  });

  it('reports mismatched passwords', async () => {
    setup();
    await userEvent.type(screen.getByLabelText(/^Password/, { selector: 'input' }), 'Seva-Kitchen-42!');
    await userEvent.type(screen.getByLabelText(/Confirm password/), 'Seva-Kitchen-43!');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument();
  });

  it('offers the exact Mandal values', () => {
    setup();
    const options = Array.from(screen.getByLabelText(/Mandal name/).querySelectorAll('option')).map((o) => o.textContent);
    expect(options).toEqual(['Select', 'Edison', 'Jersey City', 'Clifton', 'Parsippany', 'Passaic', 'Pennsylvania']);
  });
});
