import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '@/test/render';
import ErrorMessage from './ErrorMessage';
import LoadingSpinner from './LoadingSpinner';
import SuccessMessage from './SuccessMessage';

describe('common components', () => {
  it('renders error and success alerts', () => {
    renderWithProviders(
      <>
        <ErrorMessage message="失败" />
        <SuccessMessage message="成功" />
      </>
    );
    expect(screen.getByText('失败')).toBeInTheDocument();
    expect(screen.getByText('成功')).toBeInTheDocument();
  });

  it('renders a loading spinner', () => {
    const { container } = renderWithProviders(<LoadingSpinner />);
    expect(container.querySelector('.center-spinner')).toBeInTheDocument();
  });
});
