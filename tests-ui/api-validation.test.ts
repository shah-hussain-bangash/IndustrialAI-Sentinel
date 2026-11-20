import test from 'node:test';
import assert from 'node:assert/strict';
import { validationMessage, api, ApiError } from '../src/api.ts';

test('password validation errors retain actionable field guidance', () => {
  const result = validationMessage([{loc:['body','password'],msg:'Value error, Choose a new password different from the shared demo password.',type:'value_error'}]);
  assert.equal(result.fields.password,'Choose a new password different from the shared demo password.');
  assert.match(result.message,/password: Choose a new password/);
});

test('API exceptions expose password validation without request values', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({detail:[{loc:['body','password'],msg:'Value error, Choose a unique password of 15–128 characters.',type:'value_error'}]}),{status:422});
  try {
    await assert.rejects(api('/team'), (error: unknown) => {
      assert.ok(error instanceof ApiError);
      assert.match(error.fields.password,/15–128/);
      return true;
    });
  } finally { globalThis.fetch=originalFetch; }
});

test('existing string errors and unexpected response shapes remain readable', () => {
  assert.equal(validationMessage('Email already exists.').message,'Email already exists.');
  for (const detail of [undefined,null,{},[],[{}]]) assert.match(validationMessage(detail).message,/check the form/);
});
