using System;
using System.Collections.Generic;

namespace Example.Services
{
    /// <summary>
    /// Sample C# service class for testing.
    /// </summary>
    public class CustomerService
    {
        private readonly List<string> _customers = new List<string>();

        public void RegisterCustomer(string name)
        {
            if (!string.IsNullOrEmpty(name))
            {
                _customers.Add(name);
            }
        }

        public int CustomerCount()
        {
            return _customers.Count;
        }
    }
}
