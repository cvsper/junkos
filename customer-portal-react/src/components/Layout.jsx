import React from 'react';
import { Trash2 } from 'lucide-react';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-primary-600 p-2 rounded-lg">
                <Trash2 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Umuve</h1>
                <p className="text-sm text-gray-500">Hauling made simple.</p>
              </div>
            </div>
            <div className="hidden sm:block">
              <a
                href="tel:1-800-UMUVE"
                className="text-primary-600 hover:text-primary-700 font-medium"
              >
                📞 1-800-UMUVE
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col items-center gap-4">
            <div className="flex items-center gap-4 text-sm text-green-700 font-medium">
              <span className="flex items-center gap-1.5">&#10084;&#65039; Donate First</span>
              <span className="text-gray-300">|</span>
              <span className="flex items-center gap-1.5">&#9851;&#65039; Recycle &amp; Reuse</span>
              <span className="text-gray-300">|</span>
              <span className="flex items-center gap-1.5">&#127758; Landfill Last</span>
            </div>
            <p className="text-xs text-gray-500 text-center max-w-lg">
              We partner with local charities, shelters, and recycling centers.
              Usable items are donated before anything is disposed of. Donation
              receipts provided for tax purposes when applicable.
            </p>
            <div className="text-center text-gray-600 text-sm">
              <p>&copy; {new Date().getFullYear()} Umuve. All rights reserved.</p>
              <div className="mt-2 space-x-4">
                <a href="#" className="hover:text-primary-600">Privacy Policy</a>
                <span>&bull;</span>
                <a href="#" className="hover:text-primary-600">Terms of Service</a>
                <span>&bull;</span>
                <a href="#" className="hover:text-primary-600">Contact Us</a>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
